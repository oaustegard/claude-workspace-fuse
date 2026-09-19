"""
backup.py — Dump the Muninn memory store and commit it to the backup repo.

WHY THIS EXISTS: before 2026-09-17 the only snapshot in oaustegard/muninn-backup
was from 2026-03-05, six and a half months stale and encrypted to an X25519 key
whose identity file is lost — an unrecoverable backup, which is the same as none.
It was stale because the export path stopped one step short: remembering's
scripts/export.py writes a PLAINTEXT dump "for optional encryption later", and
both the encryption and the commit were manual. Manual steps that nobody
schedules do not happen, and manual steps that leave no memory cannot even be
audited afterwards. This module does dump -> gzip -> commit -> record in one
call so there is no step left for a human to skip.

CADENCE: run_backup() self-skips unless MIN_DAYS have passed, the same hard-floor
pattern zeitgeist uses. Safe to call on every sleep run.

ENCRYPTION: none. Oskar declined a keypair on 2026-09-17; the repo being private
is the only control. Snapshots contain EVERY memory, including confidential-tagged
career-search and health-private scopes. Do not make that repo public, fork it,
or mirror it anywhere less private. If a key is ever generated, encrypt here —
inside the function — so the step cannot be skipped again.

Usage:
    from muninn_utils.backup import run_backup
    result = run_backup()            # cadence-gated; returns {'status': 'skipped'|'ok'}
    result = run_backup(force=True)  # ignore cadence
"""
import gzip
import io
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/New_York")  # Oskar's timezone; snapshots are stamped in it
REPO = "oaustegard/muninn-backup"
SNAPSHOT_DIR = "snapshots"
MIN_DAYS = 6  # weekly with a one-day buffer, so a sleep run a few hours early still backs up

# FTS tables are derived from `memories` and rebuild on restore; committing them
# would roughly double the artifact for no recovery value.
TABLES = ["memories", "config", "relay_messages", "tag_cooccurrence"]
PAGE = 500

BACKUP_TAGS = ["muninn-backup", "snapshot", "backup"]


class BackupError(RuntimeError):
    """Raised when a backup cannot be completed. Never swallowed — a silent
    backup failure is indistinguishable from a backup that never ran, which is
    the exact failure this module exists to end."""


def _utcnow():
    return datetime.now(timezone.utc)


def days_since_last_backup():
    """Days since the last SUCCESSFUL backup, or None if there has never been one.

    Reads the memory trail rather than the repo tree: the memory is written only
    after the commit lands, so it cannot claim a backup that failed mid-push.
    """
    from scripts import recall

    best = None
    for r in recall(tags=["muninn-backup", "snapshot"], tag_mode="all", n=10):
        stamp = r.get("valid_from") or r.get("created_at")
        if not stamp:
            continue
        try:
            when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if best is None or when > best:
            best = when
    if best is None:
        return None
    return (_utcnow() - best).total_seconds() / 86400.0


def dump_tables(tables=None):
    """Page every row of each table into {table: {columns, rows}}."""
    from scripts.turso import _exec

    tables = tables or TABLES
    out = {}
    for t in tables:
        columns = [r["name"] for r in _exec(f"PRAGMA table_info({t})")]
        if not columns:
            raise BackupError(f"table {t!r} has no columns — wrong DB or renamed table")
        rows, offset = [], 0
        while True:
            batch = _exec(f"SELECT * FROM {t} LIMIT {PAGE} OFFSET {offset}")
            if not batch:
                break
            rows.extend(batch)
            offset += PAGE
            if len(batch) < PAGE:
                break
        out[t] = {"columns": columns, "rows": rows}
    if not out.get("memories", {}).get("rows"):
        raise BackupError("dump contains zero memories — refusing to commit an empty backup")
    return out


def gzip_bytes(payload):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        gz.write(json.dumps(payload).encode())
    return buf.getvalue()


def snapshot_name(when=None):
    """Stamp the file with OSKAR'S local date, not UTC.

    A backup run during a US evening lands after midnight UTC, so a naive
    utcnow() stamp reads a day ahead of the day it was taken — the recurring
    date-grounding failure this system already has a rule against. Proven here
    on 2026-09-17: the first forced run wrote ...2026-09-18.json.gz at 21:2x EDT.
    """
    when = when or _utcnow()
    return f"muninn-memory-backup-{when.astimezone(LOCAL_TZ).strftime('%Y-%m-%d')}.json.gz"


def run_backup(*, force=False, min_days=MIN_DAYS, repo=REPO, store=True):
    """Dump, gzip, commit, record. Returns a dict; raises BackupError on failure.

    status 'skipped' — cadence floor not met, nothing done, nothing stored.
    status 'ok'      — commit landed; 'commit' and 'path' identify it.
    """
    from muninn_utils.gh_proxy import commit_files, valid_token

    age = days_since_last_backup()
    if not force and age is not None and age < min_days:
        return {"status": "skipped", "days_since_last": round(age, 1),
                "min_days": min_days}

    # Check the credential BEFORE spending a full dump on a push that cannot land.
    # GH_TOKEN ships preset to the truthy placeholder 'proxy-injected', so a
    # presence check passes with no real credential and fails later as a 401.
    if not valid_token(os.environ.get("GH_TOKEN")):
        raise BackupError(
            "no usable GitHub token — GH_TOKEN is absent or still the "
            "'proxy-injected' placeholder. Source GitHub.env before calling."
        )

    payload = dump_tables()
    blob = gzip_bytes(payload)
    name = snapshot_name()
    path = f"{SNAPSHOT_DIR}/{name}"
    counts = {t: len(v["rows"]) for t, v in payload.items()}

    message = (
        f"Add memory snapshot {name}\n\n"
        + ", ".join(f"{k}: {v}" for k, v in counts.items())
        + "\n\nAutomated weekly backup via muninn_utils.backup.run_backup().\n"
        "Plaintext by decision (2026-09-17) — repo privacy is the only control.\n"
    )

    result = commit_files(repo, "main", {path: blob}, message,
                          base="main", new_branch=False)

    record = {
        "status": "ok",
        "path": path,
        "bytes": len(blob),
        "counts": counts,
        "commit": result["commit"],
        "url": result.get("url"),
        "days_since_last": None if age is None else round(age, 1),
    }

    if store:
        from scripts import remember
        remember(
            f"BACKUP {name} committed to {repo} ({result['commit'][:8]}), "
            f"{len(blob)} bytes gzipped. Rows: "
            + ", ".join(f"{k} {v}" for k, v in counts.items())
            + ". Gap since previous backup: "
            + ("first automated run" if age is None else f"{age:.1f} days")
            + ". Plaintext, private repo.",
            type="procedure", tags=BACKUP_TAGS + [_utcnow().astimezone(LOCAL_TZ).strftime("%Y-%m-%d")],
            priority=0,
        )

    return record


if __name__ == "__main__":
    import sys
    print(json.dumps(run_backup(force="--force" in sys.argv), indent=2))
