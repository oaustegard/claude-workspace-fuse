"""Reminder utilities for Muninn v2. SQL-precision queries, recurring support, snooze.

PARTIAL-INDEX CONTRACT (2026-08-01) — read before editing any query in this file.

Reminder state lives in the `tags` JSON blob, so every lookup here is a
leading-wildcard `tags LIKE '%"remind-<state>"%'`, which no ordinary index can
serve. On Turso that degraded into a full remote scan of `memories`: 5,063 rows
read, ~46 s server-side, which exceeds the 30 s client timeout and so *failed
boot* rather than merely running slow (the table averages ~1.6 KB per summary,
so a scan drags the whole table across the wire).

The fix is one partial index per state, keyed on `valid_from`:

    CREATE INDEX idx_memories_remind_<state> ON memories(valid_from)
    WHERE deleted_at IS NULL AND tags LIKE '%"remind-<state>"%'

Each index materialises only the handful of rows in that state, so the scan
never happens. Measured on the live DB: 46,190 ms / 5,063 rows read -> 69 ms /
16 rows read.

TWO CONSTRAINTS THIS IMPOSES ON QUERIES BELOW:

1. SQLite only uses a partial index when it can prove the index's WHERE clause
   from the query's WHERE clause, which in practice means the query must
   contain `deleted_at IS NULL AND tags LIKE '%"remind-<state>"%'` as literal
   AND-ed terms. Keep the tag pattern inline; do NOT parameterise it, do not
   fold it into a computed expression, and do not relax it to a broader pattern
   like `'%remind%'` (the planner cannot prove the narrow term implies it).

2. An OR of state predicates defeats the proof entirely — SQLite's OR
   optimisation will not reason across partial indexes and falls back to a full
   scan. `remind_list()` therefore issues a UNION ALL of per-state SELECTs, not
   `WHERE (A OR B)`. Measured: the OR form still took 47,052 ms / 5,079 rows;
   the UNION ALL form takes 108 ms / 17 rows. If you add a state, add its index
   to REMIND_STATES and give it its own UNION arm.
"""

import json, re
from datetime import datetime, timezone, timedelta
from scripts import remember as _remember, _exec

UTC = timezone.utc

#: Reminder states that get a dedicated partial index. Order is not significant.
REMIND_STATES = ("remind-active", "remind-snoozed", "remind-done")

_INDEXES_ENSURED = False


def _ensure_remind_indexes():
    """Idempotently create the per-state partial indexes.

    Self-healing on existing databases: `bootstrap.py` creates these for fresh
    ones, but deployments that predate 2026-08-01 have the table without them,
    and the symptom (boot timing out) gives no hint that a DDL step is missing.
    Runs at most once per process; `CREATE INDEX IF NOT EXISTS` on an index that
    already exists is a catalogue lookup, not a scan, so the cost is noise.

    Best-effort: a failure here leaves the old slow-but-correct behaviour, so it
    must never propagate and break a caller.
    """
    global _INDEXES_ENSURED
    if _INDEXES_ENSURED:
        return
    _INDEXES_ENSURED = True  # set first: one attempt per process, even on failure
    for state in REMIND_STATES:
        try:
            _exec(
                f"""CREATE INDEX IF NOT EXISTS idx_memories_{state.replace('-', '_')}
                    ON memories(valid_from)
                    WHERE deleted_at IS NULL AND tags LIKE '%"{state}"%'""")
        except Exception:  # noqa: BLE001, S110 - DDL is best-effort; queries stay correct without it
            pass


def remind(what, due=None, *, kind="nag", recur_days=None, alert_before_days=None, tags=None, priority=1):
    """Create a reminder.
    
    Args:
        what: What to remind about (plain text)
        due: ISO date/datetime, relative shorthand (+3d, tomorrow, next week), or None for now
        kind: "nag" (every boot until done) or "notice" (surface once then auto-done)
        recur_days: Recurring every N days — completing resets due date forward
        alert_before_days: Start showing N days before due date
        tags: Additional topic tags
        priority: Memory priority (default 1)
    
    Returns: memory id
    """
    due_iso = _parse_when(due) if due else datetime.now(UTC).isoformat().replace("+00:00", "Z")
    meta = {"kind": kind}
    if recur_days: meta["recur_days"] = recur_days
    if alert_before_days: meta["alert_before_days"] = alert_before_days
    summary = f"REMIND: {what}\nMETA: {json.dumps(meta)}"
    all_tags = ["remind", "remind-active", f"remind-{kind}"]
    if tags: all_tags.extend(tags)
    return _remember(summary, type="procedure", tags=all_tags, valid_from=due_iso, priority=priority)


def remind_done(reminder_id, *, note=None):
    """Complete a reminder. Recurring: resets due forward. One-shot: marks done.
    
    Args:
        reminder_id: Full or 8-char prefix of reminder id
        note: Optional completion note
    
    Returns: status string
    """
    row = _find_reminder(reminder_id)
    if not row: return f"Reminder {reminder_id} not found"
    rid, summary = row["id"], row["summary"]
    tags = json.loads(row["tags"]) if isinstance(row["tags"], str) else (row["tags"] or [])
    meta = _parse_meta(summary)
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    now_short = now_iso[:10]
    recur_days = meta.get("recur_days")
    if recur_days:
        next_due = (datetime.now(UTC) + timedelta(days=recur_days)).isoformat().replace("+00:00", "Z")
        completion = f"\nCOMPLETED: {now_short}" + (f" — {note}" if note else "")
        clean = re.sub(r"\nCOMPLETED:.*", "", summary)
        _exec("UPDATE memories SET summary = ?, valid_from = ?, updated_at = ? WHERE id = ?",
              [clean + completion, next_due, now_iso, rid])
        return f"Recurring reminder reset. Next due: {next_due[:10]}"
    else:
        new_tags = [t for t in tags if t not in ("remind-active", "remind-snoozed")]
        new_tags.append("remind-done")
        done_note = f"\nDONE: {now_short}" + (f" — {note}" if note else "")
        _exec("UPDATE memories SET summary = ?, tags = ?, updated_at = ? WHERE id = ?",
              [summary + done_note, json.dumps(new_tags), now_iso, rid])
        return f"Reminder {rid[:8]} marked done"


def remind_snooze(reminder_id, until):
    """Snooze a reminder until a given date/time.
    
    Args:
        reminder_id: Full or 8-char prefix of reminder id
        until: ISO date/datetime or relative shorthand (+3d, tomorrow)
    
    Returns: status string
    """
    row = _find_reminder(reminder_id)
    if not row: return f"Reminder {reminder_id} not found"
    rid = row["id"]
    tags = json.loads(row["tags"]) if isinstance(row["tags"], str) else (row["tags"] or [])
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    snooze_until = _parse_when(until)
    new_tags = [t for t in tags if t not in ("remind-active", "remind-snoozed")]
    new_tags.append("remind-snoozed")
    _exec("UPDATE memories SET tags = ?, valid_from = ?, updated_at = ? WHERE id = ?",
          [json.dumps(new_tags), snooze_until, now_iso, rid])
    return f"Snoozed until {snooze_until[:10]}"


def remind_due(horizon_days=2):
    """Get reminders due now or upcoming within horizon. SQL precision, no fuzzy search.
    
    Used by boot and in-conversation checks.
    Returns list of dicts: id, text, valid_from, kind, recur_days, status
    Status values: overdue, due, upcoming (Nd)
    """
    _ensure_remind_indexes()
    now = datetime.now(UTC)
    now_iso = now.isoformat().replace("+00:00", "Z")
    horizon_iso = (now + timedelta(days=horizon_days)).isoformat().replace("+00:00", "Z")
    
    active = _exec(
        """SELECT id, summary, valid_from, tags FROM memories
           WHERE deleted_at IS NULL AND tags LIKE '%"remind-active"%'
             AND valid_from <= ? ORDER BY valid_from ASC""", [horizon_iso]) or []
    
    # Un-snooze expired snoozed reminders
    snoozed = _exec(
        """SELECT id, summary, valid_from, tags FROM memories
           WHERE deleted_at IS NULL AND tags LIKE '%"remind-snoozed"%'
             AND valid_from <= ? ORDER BY valid_from ASC""", [now_iso]) or []
    for s in snoozed:
        stags = json.loads(s["tags"]) if isinstance(s["tags"], str) else s["tags"]
        new_tags = [t for t in stags if t != "remind-snoozed"] + ["remind-active"]
        _exec("UPDATE memories SET tags = ?, updated_at = ? WHERE id = ?",
              [json.dumps(new_tags), now_iso, s["id"]])
    
    # Future items with advance alerts
    future_alert = _exec(
        """SELECT id, summary, valid_from, tags FROM memories
           WHERE deleted_at IS NULL AND tags LIKE '%"remind-active"%'
             AND valid_from > ? AND summary LIKE '%alert_before_days%'
           ORDER BY valid_from ASC""", [horizon_iso]) or []
    
    results, seen = [], set()
    for row in active + snoozed + future_alert:
        if row["id"] in seen: continue
        seen.add(row["id"])
        meta = _parse_meta(row["summary"])
        vf = row.get("valid_from", "")
        if vf <= now_iso:
            status = "overdue" if vf < now_iso[:10] else "due"
        else:
            alert_days = meta.get("alert_before_days", 0)
            if alert_days:
                due_dt = datetime.fromisoformat(vf.replace("Z", "+00:00"))
                if now >= due_dt - timedelta(days=alert_days):
                    status = f"upcoming ({(due_dt - now).days}d)"
                else: continue
            elif vf <= horizon_iso:
                status = f"upcoming ({(datetime.fromisoformat(vf.replace('Z', '+00:00')) - now).days}d)"
            else: continue
        results.append({"id": row["id"], "text": _clean_summary(row["summary"]),
            "valid_from": vf, "kind": meta.get("kind", "nag"),
            "recur_days": meta.get("recur_days"), "status": status})
    return results


def remind_list(include_done=False):
    """List all reminders with SQL precision.
    
    Returns list of dicts: id, text, valid_from, kind, recur_days, state (active|snoozed|done)
    """
    _ensure_remind_indexes()
    states = ["remind-active", "remind-snoozed"]
    if include_done: states.append("remind-done")
    # UNION ALL, not `WHERE (A OR B)` — see the partial-index contract in the
    # module docstring. The OR form cannot use the per-state indexes and full-
    # scans the table (47 s); this form is index-served (0.1 s). Rows are
    # disjoint by construction (a reminder holds exactly one state tag), so
    # UNION ALL is correct and avoids a dedupe sort.
    arms = "\n      UNION ALL\n".join(
        f"""SELECT id, summary, valid_from, tags FROM memories
        WHERE deleted_at IS NULL AND tags LIKE '%"{s}"%'""" for s in states)
    rows = _exec(f"{arms}\n      ORDER BY valid_from ASC") or []
    results = []
    for row in rows:
        meta = _parse_meta(row["summary"])
        tags = json.loads(row["tags"]) if isinstance(row["tags"], str) else row["tags"]
        state = "done" if "remind-done" in tags else ("snoozed" if "remind-snoozed" in tags else "active")
        results.append({"id": row["id"], "text": _clean_summary(row["summary"]),
            "valid_from": row.get("valid_from", ""), "kind": meta.get("kind", "nag"),
            "recur_days": meta.get("recur_days"), "state": state})
    return results


def remind_sweep(*, archive_after_days=21, missed_cycles=2, dry_run=True):
    """Move stale reminders out of the active surface.

    Multica-style sweeper: reminders overdue for a long time without being
    acknowledged (completed, snoozed, or re-scheduled) are dead weight, not
    signal. Sweep them to `remind-stale` so the active list stays a live
    queue, not an archive.

    Args:
        archive_after_days: One-shot reminders overdue by more than this many
            days get swept. Default 21.
        missed_cycles: Recurring reminders whose valid_from is older than
            (recur_days * missed_cycles) days get swept. Default 2 — a 14-day
            recurring that hasn't been touched in 28d is stale.
        dry_run: If True (default), return what WOULD be swept without
            changing anything. Call with dry_run=False to commit.

    Returns:
        {"swept": [{id, text, kind, overdue_days, reason}, ...],
         "kept": int, "dry_run": bool}
    """
    now = datetime.now(UTC)
    now_iso = now.isoformat().replace("+00:00", "Z")

    # Only scan currently-active reminders. Snoozed are intentionally deferred.
    rows = _exec("""SELECT id, summary, valid_from, tags FROM memories
                    WHERE deleted_at IS NULL
                      AND tags LIKE '%"remind-active"%'
                      AND valid_from < ?""", [now_iso]) or []

    swept, kept = [], 0
    for row in rows:
        vf = row.get("valid_from") or ""
        try:
            due_dt = datetime.fromisoformat(vf.replace("Z", "+00:00"))
        except ValueError:
            kept += 1
            continue
        overdue_days = (now - due_dt).days
        meta = _parse_meta(row["summary"])
        recur_days = meta.get("recur_days")

        should_sweep, reason = False, None
        if recur_days:
            threshold = recur_days * missed_cycles
            if overdue_days >= threshold:
                should_sweep = True
                reason = f"recurring, overdue {overdue_days}d (threshold {threshold}d = {recur_days}d x {missed_cycles})"
        else:
            if overdue_days >= archive_after_days:
                should_sweep = True
                reason = f"one-shot, overdue {overdue_days}d (threshold {archive_after_days}d)"

        if not should_sweep:
            kept += 1
            continue

        swept.append({
            "id": row["id"],
            "text": _clean_summary(row["summary"])[:100],
            "kind": "recurring" if recur_days else "one-shot",
            "overdue_days": overdue_days,
            "reason": reason,
        })

        if not dry_run:
            tags = json.loads(row["tags"]) if isinstance(row["tags"], str) else (row["tags"] or [])
            new_tags = [t for t in tags if t not in ("remind-active", "remind-snoozed")]
            new_tags.append("remind-stale")
            stale_note = f"\nSTALE: {now_iso[:10]} - {reason}"
            _exec("UPDATE memories SET tags = ?, summary = ?, updated_at = ? WHERE id = ?",
                  [json.dumps(new_tags), row["summary"] + stale_note, now_iso, row["id"]])

    return {"swept": swept, "kept": kept, "dry_run": dry_run}


# === INTERNALS ===

def _find_reminder(id_or_prefix):
    rows = _exec("SELECT id, summary, tags, valid_from FROM memories WHERE id = ? AND deleted_at IS NULL",
                 [id_or_prefix])
    if rows: return rows[0]
    rows = _exec(
        "SELECT id, summary, tags, valid_from FROM memories WHERE id LIKE ? AND deleted_at IS NULL AND tags LIKE '%remind%'",
        [id_or_prefix + "%"])
    if rows and len(rows) == 1: return rows[0]
    return None

def _parse_meta(summary):
    for line in summary.split("\n"):
        if line.startswith("META: "):
            try: return json.loads(line[6:])
            except: return {}
    return {}

def _clean_summary(summary):
    lines = []
    for line in summary.split("\n"):
        if line.startswith("META: ") or line.startswith("COMPLETED: ") or line.startswith("DONE: ") or line.startswith("STALE: "): continue
        if line.startswith("REMIND: "): lines.append(line[8:])
        elif line.startswith("REMINDER: "): lines.append(line[10:])
        else: lines.append(line)
    return "\n".join(lines).strip()

def _parse_when(when):
    if not when: return datetime.now(UTC).isoformat().replace("+00:00", "Z")
    if "T" in when: return when
    if len(when) == 10 and "-" in when: return when + "T00:00:00Z"
    now = datetime.now(UTC)
    low = when.lower().strip()
    rel = re.match(r"(?:in\s+)?\+?(\d+)\s*(m|min|minutes?|h|hours?|d|days?|w|weeks?)", low)
    if rel:
        n, unit = int(rel.group(1)), rel.group(2)[0]
        deltas = {"m": timedelta(minutes=n), "h": timedelta(hours=n),
                  "d": timedelta(days=n), "w": timedelta(weeks=n)}
        return (now + deltas[unit]).isoformat().replace("+00:00", "Z")
    if low == "tomorrow":
        return (now + timedelta(days=1)).replace(hour=13, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
    if low == "next week":
        return (now + timedelta(weeks=1)).replace(hour=13, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
    return when
