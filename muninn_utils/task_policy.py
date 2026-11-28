"""Task policy loader for perch autonomous tasks.

Each perch task (zeitgeist, fly, sleep, dispatch) has policy that evolves
over time as Oskar's preferences shift. That policy lives in two places:

  - The {task}-command ops entry (authoritative, edited via config_set)
  - Preference memories tagged with the task name (context, recent signals)

This utility loads both, plus the most recent run of the task, so task
prompts can route to the live policy instead of hardcoding behavior that
goes stale the moment a preference changes.

See oaustegard/muninn-utilities#14 for the architectural background.
"""

from datetime import datetime, timezone
from scripts import config_get, recall, _exec


def load(task_name: str, *, n_prefs: int = 5) -> dict:
    """Load the live policy for a perch task.

    Args:
        task_name: e.g. "zeitgeist", "fly", "sleep", "dispatch"
        n_prefs: max number of preference memories to surface

    Returns:
        dict with keys:
          - instructions: str | None — the {task_name}-command ops entry,
            None if no such entry exists
          - preferences: list — recent memories tagged with both the task
            name and "preference"
          - last_run: dict | None — most recent memory tagged with the
            task name (excluding skip-logs), with id/valid_from/type/tags/summary
    """
    # 1. Ops entry — the authoritative spec
    try:
        instructions = config_get(f'{task_name}-command')
    except Exception:
        instructions = None

    # 2. Recent preference signals
    try:
        prefs_result = recall(tags=[task_name, 'preference'], tag_mode='all', n=n_prefs)
        preferences = list(prefs_result) if prefs_result else []
    except Exception:
        preferences = []

    # 3. Last real run (scope to perch-time autonomous runs; exclude skip-logs)
    last_run = None
    try:
        skip_tag = f'{task_name}-skip'
        rows = _exec(
            "SELECT id, valid_from, type, tags, substr(summary,1,300) as summary "
            "FROM memories "
            "WHERE deleted_at IS NULL "
            "  AND is_superseded = 0 "
            "  AND tags LIKE '%\"perch-time\"%' "
            "  AND tags LIKE ? "
            "  AND tags NOT LIKE ? "
            "ORDER BY valid_from DESC "
            "LIMIT 1",
            (f'%"{task_name}"%', f'%"{skip_tag}"%'),
        )
        if rows:
            last_run = rows[0]
    except Exception:
        last_run = None

    return {
        'instructions': instructions,
        'preferences': preferences,
        'last_run': last_run,
    }


def days_since_last_run(policy: dict) -> float | None:
    """Return days elapsed since policy['last_run'], or None if no prior run."""
    last = policy.get('last_run')
    if not last:
        return None
    try:
        raw = last['valid_from'].replace('Z', '+00:00')
        dt = datetime.fromisoformat(raw)
        now = datetime.now(timezone.utc)
        return (now - dt).total_seconds() / 86400
    except Exception:
        return None


def format_summary(policy: dict, task_name: str) -> str:
    """Human-readable one-paragraph summary of loaded policy, for logging."""
    parts = []
    if policy.get('instructions'):
        parts.append(f"{task_name}-command ops entry loaded ({len(policy['instructions'])} chars)")
    else:
        parts.append(f"no {task_name}-command ops entry; using fallback defaults")

    n_prefs = len(policy.get('preferences') or [])
    if n_prefs:
        parts.append(f"{n_prefs} recent preference memories")

    days = days_since_last_run(policy)
    if days is not None:
        parts.append(f"last run {days:.1f}d ago")
    else:
        parts.append("no prior run on record")

    return "; ".join(parts)
