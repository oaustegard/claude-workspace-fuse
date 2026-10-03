"""Store integrity: who replaced whom, and whether the flags agree.

`refs` holds two different kinds of edge in one column. `supersede()` writes
`refs=[original_id]` on the replacement: a ledger entry saying *this replaced
that*. `remember(refs=...)` writes citations: *this rests on that*. Anything
that reads `refs` as if it held only one kind gets the other kind wrong.

That happened twice in this package. `_write_memory` used to flag every
referenced memory `is_superseded=1` (removed in v5.7.0), and the one-time
backfill that created the column did the same across the whole store. Both
treated "cited by a live memory" as "replaced". Measured 2026-09-17: 57 live
memories carried the flag with no replacement anywhere, so recall had been
hiding them. The same conflation made `memory_lint` count every supersede
edge as a stale citation (claude-workspace#231).

dmarx/luria states the general rule as its DP-13: a mechanism's own record,
spelled in the pattern it matches, is misread by every other matcher of that
pattern, so the exclusion belongs in each matcher. The fix here is to stop
inferring and store the edge: `superseded_by` names the replacement on the
retired row, and `supersede()` writes it in the same statement that retires
the original.

For rows written before the column existed, the edge is recovered from the
signature `supersede()` leaves, which is exact rather than heuristic:

  * the original has `deleted_at` set,
  * the replacement's `refs` is a JSON list of exactly one bare string equal
    to the original's full id,
  * and the replacement's `created_at` equals the original's `deleted_at`
    character for character, because both come from one `now`.

Measured 2026-09-17: 181 of 307 retired, flagged rows match with a unique
replacement and none match ambiguously. The rest predate the signature or were
flagged by the old conflation; they stay unlinked rather than guessed at.

The pure functions take row dicts so they can be tested without a database.
`repair()` and `successor()` are the only functions that touch the store.
"""

from __future__ import annotations

import ast
import json
import re

_ID_RE = re.compile(r"\A[0-9a-fA-F][0-9a-fA-F-]{7,35}\Z")
FULL_ID_LEN = 36
MIN_PREFIX = 8

COLUMNS = "id, refs, created_at, deleted_at, is_superseded, superseded_by"


def _present(v) -> bool:
    return v not in (None, "", "None")


def _truthy(v) -> bool:
    return str(v) in ("1", "True", "true")


def is_full_id(s) -> bool:
    return isinstance(s, str) and len(s) == FULL_ID_LEN and s.count("-") == 4


def load_refs(raw):
    """Parse a `refs` cell into a list, or None if it cannot be parsed.

    The column holds JSON lists, Python-repr'd lists (older writers), and the
    literal string 'null'. None means "leave this cell alone"; an empty list
    means "parsed, and empty".
    """
    if raw is None or raw in ("", "null", "None"):
        return []
    if isinstance(raw, list):
        return raw
    for loader in (json.loads, ast.literal_eval):
        try:
            val = loader(raw)
        except Exception:  # noqa: BLE001 - try the next encoding
            continue
        if val is None:
            return []
        return val if isinstance(val, list) else [val]
    return None


def ref_id(item):
    """The memory id an element of `refs` points at, or None.

    Bare strings and `{"id": ...}` dicts point at memories. Typed objects
    (`{"_type": "alternatives", ...}`) and strings that are not id-shaped
    (URLs, `repo#12`) do not.
    """
    if isinstance(item, dict):
        if item.get("_type"):
            return None
        item = item.get("id")
    if isinstance(item, str) and _ID_RE.match(item):
        return item
    return None


def supersession_links(rows) -> dict:
    """{original_id: replacement_id} for every row carrying the supersede signature.

    See the module docstring for the signature. A retired row with two
    candidate replacements is left out: the data cannot say which was meant.
    """
    retired_at = {r["id"]: r.get("deleted_at") for r in rows if _present(r.get("deleted_at"))}
    candidates: dict = {}
    for r in rows:
        refs = load_refs(r.get("refs"))
        if not refs or len(refs) != 1 or not isinstance(refs[0], str):
            continue
        orig = refs[0]
        if orig == r["id"] or not is_full_id(orig):
            continue
        when = retired_at.get(orig)
        if when is not None and r.get("created_at") == when:
            candidates.setdefault(orig, []).append(r["id"])
    return {o: news[0] for o, news in candidates.items() if len(news) == 1}


def plan_repairs(rows) -> dict:
    """What `repair()` would write, computed from rows alone.

    Returns:
      link:   [(original_id, replacement_id)] where the signature holds and the
              row is missing `superseded_by` or the `is_superseded` flag.
      unflag: [id] for live rows flagged superseded with no replacement named.
              `supersede()` always retires the original, so a live flagged row
              is the old refs-as-supersede conflation, and recall hides it.
    """
    links = supersession_links(rows)
    by_id = {r["id"]: r for r in rows}
    link = []
    for orig, new in sorted(links.items()):
        r = by_id[orig]
        if r.get("superseded_by") != new or not _truthy(r.get("is_superseded")):
            link.append((orig, new))
    unflag = sorted(
        r["id"] for r in rows
        if _truthy(r.get("is_superseded"))
        and not _present(r.get("deleted_at"))
        and not _present(r.get("superseded_by"))
    )
    return {"link": link, "unflag": unflag}


def resolve_prefixes(partials, known_ids) -> dict:
    """{partial: full_id} for each partial that is a unique prefix of a known id.

    Callers wrote 8-character prefixes into `refs` for months (181 live
    references as of 2026-09-17). An exact-match lookup reads every one of
    them as a dangling pointer. Ambiguous and unmatched prefixes are left out.
    """
    known = sorted(known_ids)
    out = {}
    for p in set(partials):
        if not isinstance(p, str) or len(p) < MIN_PREFIX or p in known_ids:
            continue
        low = p.lower()
        hits = [k for k in known if k.lower().startswith(low)]
        if len(hits) == 1:
            out[p] = hits[0]
    return out


def successor_chain(start: str, links: dict, max_hops: int = 50) -> list:
    """[start, replacement, replacement's replacement, ...] over `links`.

    Stops at a row nothing replaced, at a cycle, or after `max_hops`.
    """
    chain = [start]
    seen = {start}
    cur = start
    for _ in range(max_hops):
        nxt = links.get(cur)
        if not nxt or nxt in seen:
            break
        chain.append(nxt)
        seen.add(nxt)
        cur = nxt
    return chain


# --- store access ------------------------------------------------------------

def _load_rows():
    from .turso import _exec
    try:
        return _exec(f"SELECT {COLUMNS} FROM memories")
    except Exception as exc:  # noqa: BLE001
        if "superseded_by" not in str(exc):
            raise
        # Before the column exists every row reads as unlinked, which is true.
        return _exec("SELECT id, refs, created_at, deleted_at, is_superseded, "
                     "NULL AS superseded_by FROM memories")


def successor(memory_id: str, max_hops: int = 50):
    """The memory that currently stands in for `memory_id`.

    Follows `superseded_by` until a row names no replacement. Returns
    `memory_id` itself when it was never superseded, and None when no such
    memory exists. Partial ids are accepted.
    """
    from .turso import _exec

    rows = _exec("SELECT id, superseded_by FROM memories WHERE id LIKE ?", [f"{memory_id}%"])
    if len(rows) != 1:
        if len(rows) > 1:
            raise ValueError(f"Partial id '{memory_id}' matches {len(rows)} memories")
        return None
    cur, nxt = rows[0]["id"], rows[0].get("superseded_by")
    seen = {cur}
    for _ in range(max_hops):
        if not _present(nxt) or nxt in seen:
            break
        found = _exec("SELECT id, superseded_by FROM memories WHERE id = ?", [nxt])
        if not found:
            break
        cur, nxt = found[0]["id"], found[0].get("superseded_by")
        seen.add(cur)
    return cur


def repair(write: bool = False, rows=None) -> dict:
    """Plan, and with `write=True` apply, the lineage repairs.

    Links recovered supersessions (`superseded_by` + `is_superseded=1`) and
    clears the flag on live rows that nothing replaced. Returns the plan with
    counts. Reads every row once; not for the hot path.
    """
    if rows is None:
        rows = _load_rows()
    plan = plan_repairs(rows)
    plan["counts"] = {"link": len(plan["link"]), "unflag": len(plan["unflag"])}
    plan["written"] = False
    if write and (plan["link"] or plan["unflag"]):
        from .turso import _exec_batch
        stmts = [
            ("UPDATE memories SET superseded_by = ?, is_superseded = 1 WHERE id = ?", [new, orig])
            for orig, new in plan["link"]
        ] + [
            ("UPDATE memories SET is_superseded = 0 WHERE id = ? AND deleted_at IS NULL "
             "AND superseded_by IS NULL", [mid])
            for mid in plan["unflag"]
        ]
        for i in range(0, len(stmts), 100):
            _exec_batch(stmts[i:i + 100])
        plan["written"] = True
    return plan


HIDDEN_LIVE_SQL = (
    "SELECT COUNT(*) AS n FROM memories "
    "WHERE is_superseded = 1 AND deleted_at IS NULL AND superseded_by IS NULL"
)


def boot_signal(exec_fn=None) -> str:
    """One boot line when live rows are hidden by a stale superseded flag.

    Served by idx_memories_active, so it costs a few index rows, not a scan.
    Empty when the count is zero; a failed check says so rather than passing
    for a clean one.
    """
    if exec_fn is None:
        from .turso import _exec as exec_fn
    try:
        rows = exec_fn(HIDDEN_LIVE_SQL)
        n = int(rows[0].get("n", 0)) if rows else 0
    except Exception as exc:  # noqa: BLE001 - boot must not fail on this
        return f"lineage check failed: {type(exc).__name__}"
    if not n:
        return ""
    return (f"lineage: {n} live memories hidden from recall by a stale superseded flag "
            "-- run remembering.scripts.integrity.repair(write=True)")


def ensure_superseded_by_column(exec_fn=None) -> bool:
    """Add the `superseded_by` column if missing. True when it was just added.

    `exec_fn` lets a caller route the statement through its own `_exec`, so
    the one definition of this migration serves boot, bootstrap and
    supersede() alike.
    """
    if exec_fn is None:
        from .turso import _exec as exec_fn
    try:
        exec_fn("ALTER TABLE memories ADD COLUMN superseded_by TEXT")
    except Exception:  # noqa: BLE001 - the steady state: column exists
        return False
    return True
