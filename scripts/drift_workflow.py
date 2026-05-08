#!/usr/bin/env python3
"""Drift-detect → wait-for-rebuild → smoke-test → record, as a flowing graph.

Encodes the post-detection lifecycle around the container layer. Detection
itself runs in `boot-ccotw.sh:_detect_containerfile_drift` (which kicks off
`rebuild-layer.sh` in the background); this script picks up from there:

    detect_drift ──when=drifted──▶ notify ──▶ wait_for_rebuild
                                                    │
                                                    ▼
                                             smoke_test (validate=image_must_boot)
                                                    │
                              ┌─────────────────────┴──────────────────────┐
                              ▼ (detached)                                  ▼ (detached)
                       record_success                              update_drift_cache

`when=` makes the no-drift path a structural skip (notify and everything
downstream are SKIPPED automatically). `validate=` enforces the boot
contract before the success-side-effects fire. Detached tasks (auto-
discovered in flowing v1.2.0) handle bookkeeping without blocking the
critical path return.

Issue: https://github.com/oaustegard/claude-workspace/issues/53
Sibling: https://github.com/oaustegard/claude-workspace/issues/52 (smoke harness)
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parent.parent))
SKILLS_DIR = Path(os.environ.get("SKILLS_DIR", "/mnt/skills/user"))
CONTAINER_LAYER_SKILL = Path("/tmp/_container_layer")
CONTAINERFILE = PROJECT_DIR / "Containerfile"
HASH_FILE = Path("/tmp/.containerfile-hash")
REBUILD_LOG = Path("/tmp/.rebuild-layer.log")
DRIFT_RECORD = Path("/tmp/.drift-workflow-record.json")

sys.path.insert(0, str(SKILLS_DIR / "flowing" / "scripts"))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))

from flowing import Flow, task  # noqa: E402

WAIT_TIMEOUT_S = float(os.environ.get("DRIFT_WAIT_TIMEOUT_S", "1800"))  # 30 min default
WAIT_POLL_S = float(os.environ.get("DRIFT_WAIT_POLL_S", "5"))


def _hash_containerfile() -> str | None:
    """Compute the live Containerfile hash via the container-layer skill.

    Returns None if the skill is missing or hashing fails — drift detection
    then degrades to "unknown", which the gate treats as "not drifted" rather
    than triggering a spurious rebuild wait.
    """
    cli = CONTAINER_LAYER_SKILL / "scripts" / "cli.py"
    if not cli.exists() or not CONTAINERFILE.exists():
        return None
    import subprocess
    try:
        out = subprocess.run(
            ["python3", "-m", "scripts.cli", "hash", str(CONTAINERFILE)],
            cwd=str(CONTAINER_LAYER_SKILL),
            capture_output=True, text=True, timeout=15,
        )
        h = out.stdout.strip()
        return h or None
    except Exception:
        return None


@task
def detect_drift():
    """Compare live Containerfile hash to /tmp/.containerfile-hash."""
    current = _hash_containerfile()
    cached = HASH_FILE.read_text().strip() if HASH_FILE.exists() else None
    drifted = bool(current and cached and current != cached)
    return {
        "drifted": drifted,
        "current_hash": current,
        "cached_hash": cached,
    }


@task(
    depends_on=[detect_drift],
    when=lambda detect_drift: detect_drift["drifted"],
)
def notify(detect_drift):
    """Surface the drift to the operator. Stdout is read by the rebuild-status hook."""
    msg = (
        f"Containerfile drift detected: {detect_drift['cached_hash']} → "
        f"{detect_drift['current_hash']}. Rebuild in progress."
    )
    print(f"[drift] {msg}", file=sys.stderr, flush=True)
    return {"message": msg}


@task(depends_on=[notify])
def wait_for_rebuild(notify):  # noqa: ARG001 — gate dep, value unused
    """Tail /tmp/.rebuild-layer.log until DONE / FAIL / timeout.

    rebuild-layer.sh emits one-line status events: START, RESTORE, DONE
    hash=<sha>, FAIL reason=<tag>, SKIP reason=<tag>. We stop at the first
    terminal event (DONE/FAIL/SKIP) and propagate it as the task value.
    SKIP (already-running) is treated as success — another caller is
    handling the rebuild and will emit DONE on its own log line.
    """
    deadline = time.monotonic() + WAIT_TIMEOUT_S
    seen = 0
    pat = re.compile(r"^(DONE|FAIL|SKIP)\b(.*)$")

    while time.monotonic() < deadline:
        if REBUILD_LOG.exists():
            text = REBUILD_LOG.read_text()
            new = text[seen:]
            seen = len(text)
            for line in new.splitlines():
                m = pat.match(line.strip())
                if not m:
                    continue
                event, rest = m.group(1), m.group(2).strip()
                if event in ("DONE", "SKIP"):
                    return {"event": event, "detail": rest}
                # FAIL — abandon, no smoke test
                raise RuntimeError(f"rebuild failed: {rest or 'no reason given'}")
        time.sleep(WAIT_POLL_S)

    raise TimeoutError(f"rebuild did not finish within {WAIT_TIMEOUT_S:.0f}s")


def _image_must_boot(wait_for_rebuild):
    """validate= contract: the rebuild must have produced a usable image.

    DONE is the success signal; SKIP means another runner owned the rebuild
    and we trust their DONE elsewhere. Anything else means we shouldn't run
    the smoke harness against an unbuilt image.
    """
    ev = wait_for_rebuild.get("event")
    if ev not in ("DONE", "SKIP"):
        raise ValueError(f"rebuild produced no image (event={ev!r})")


@task(depends_on=[wait_for_rebuild], validate=_image_must_boot)
def smoke_test(wait_for_rebuild):  # noqa: ARG001 — gate dep
    """Run the smoke harness against the freshly-built image.

    Imports from the sibling script rather than re-shelling, so the
    aggregated report dict is preserved as the task value for downstream
    side-effects.
    """
    from smoke_test import run_smoke
    rep = run_smoke()
    if not rep["ok"]:
        raise RuntimeError(
            f"smoke harness reported {rep['n_failed']}/{rep['n_checks']} failures: "
            f"{rep['failed_names']}"
        )
    return rep


@task(depends_on=[smoke_test, detect_drift], detached=True)
def record_success(smoke_test, detect_drift):
    """Side-effect: persist a success record so subsequent boots know the
    rebuild was verified end-to-end. Detached so a bookkeeping failure
    doesn't sink the workflow's success signal."""
    record = {
        "ts": int(time.time()),
        "outcome": "success",
        "from_hash": detect_drift["cached_hash"],
        "to_hash": detect_drift["current_hash"],
        "n_checks": smoke_test["n_checks"],
    }
    DRIFT_RECORD.write_text(json.dumps(record, indent=2))
    return record


@task(depends_on=[smoke_test, detect_drift], detached=True)
def update_drift_cache(smoke_test, detect_drift):  # noqa: ARG001 — gate dep
    """Side-effect: write the new hash to /tmp/.containerfile-hash so the
    next boot's drift check reads the post-rebuild hash. Only runs after
    smoke_test passes — we never promote an unverified hash."""
    new_hash = detect_drift["current_hash"]
    if not new_hash:
        raise RuntimeError("no current_hash to promote")
    HASH_FILE.write_text(new_hash)
    return {"promoted": new_hash}


def main(argv):
    flow = Flow(smoke_test)
    flow.run()
    res = flow.results

    # Print a compact human-readable summary for the rebuild-status surface.
    drift = res["detect_drift"].value if "detect_drift" in res else None
    if drift and not drift["drifted"]:
        print("[drift] no drift detected — workflow exited via when=False gate")
        return 0

    smoke = res.get("smoke_test")
    if smoke and smoke.value:
        print(f"[drift] smoke ok — {smoke.value['n_checks']} checks passed")
        return 0

    print("[drift] workflow did not complete cleanly:", file=sys.stderr)
    for name, r in res.items():
        print(f"  {name}: {r.state.value}"
              + (f" ({r.error})" if r.error else ""), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
