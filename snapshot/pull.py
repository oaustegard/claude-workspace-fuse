"""Pull config and memories from the live Muninn DB.

All reads go through `remembering.scripts.turso._exec` which the boot
already wires into sys.path. No new DB code here — we ride on the
established client.
"""

from __future__ import annotations
import ast
import json
from typing import Iterable

from scripts.turso import _exec


def _parse_tags(raw: str) -> list[str]:
    """Parse a tags field tolerantly.

    Some memories have tags as a proper JSON array. A handful have them as
    a single JSON-encoded string whose value is a Python-repr list with
    single quotes (e.g. `"['a', 'b']"`). Try json first, then
    ast.literal_eval on the inner string, then bail.
    """
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if isinstance(parsed, list):
        return [t for t in parsed if isinstance(t, str)]
    if isinstance(parsed, str):
        try:
            inner = ast.literal_eval(parsed)
            if isinstance(inner, list):
                return [t for t in inner if isinstance(t, str)]
        except (ValueError, SyntaxError):
            pass
    return []


def pull_profile() -> list[dict]:
    """Profile config entries, alphabetical by key."""
    return _exec(
        "SELECT key, value, category, boot_load FROM config "
        "WHERE category = 'profile' ORDER BY key",
        parse_json=False,
    )


def pull_ops() -> list[dict]:
    """Ops config entries (boot_load=1 only), alphabetical by key."""
    return _exec(
        "SELECT key, value, category, boot_load FROM config "
        "WHERE category = 'ops' AND boot_load = 1 ORDER BY key",
        parse_json=False,
    )


def pull_ops_topics() -> dict[str, list[str]]:
    """Topic → ops-keys mapping; used to preserve section structure."""
    rows = _exec(
        "SELECT value FROM config WHERE key = 'ops-topics'",
        parse_json=False,
    )
    if not rows:
        return {}
    return json.loads(rows[0]["value"])


def pull_memories(
    types: Iterable[str],
    min_priority: int = 1,
    limit: int | None = None,
) -> list[dict]:
    """Surviving memories before tag/body filter.

    Returns rows with parsed `tags` (list[str]). `summary` is the body.
    """
    types_clause = ",".join(f"'{t}'" for t in types)
    sql = (
        "SELECT id, type, summary, tags, refs, priority, created_at "
        "FROM memories WHERE deleted_at IS NULL AND is_superseded = 0 "
        f"AND priority >= {int(min_priority)} "
        f"AND type IN ({types_clause}) "
        "ORDER BY priority DESC, created_at DESC"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"

    rows = _exec(sql, parse_json=False)
    for r in rows:
        r["tags"] = _parse_tags(r["tags"])
    return rows
