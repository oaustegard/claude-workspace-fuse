"""inbox_heartbeat — move a surface's watermark only when that surface was read.

WHY THIS EXISTS (as of 2026-10-08)
----------------------------------
The inbox routine keeps one watermark per surface in its state dict, for
example ``state["bluesky"]["last_checked"]``. Its procedure ended every run by
bumping every surface's heartbeat. Four sessions in the 2026-10-08 sweep did
exactly that: they fetched three surfaces that printed nothing (or printed only
HTTP status codes), wrote "nothing new", and bumped all four heartbeats. The
watermark moved past items nobody had read. One run skipped 14 unseen mentions,
including a reply that was never sent.

The bug was in the procedure, not in any single fetch. An empty fetch and a
failed fetch look identical at the end of a run unless the caller has to say
which one happened. This module makes it say so:

    counts = {"muninns-inbox": 3, "bluesky": 0, "bluesky-dms": None,
              "flight-log-comments": 1}
    report = commit_heartbeats(state, counts, now)

* an int bumps that surface's ``last_checked`` to ``now``. Zero is a real,
  empty result and the watermark may move;
* ``None`` means the fetch failed, raised, or was skipped, so the watermark
  holds where it was;
* a surface present in ``state`` but absent from ``counts`` raises. A surface
  nobody reported on is not an empty surface. A count for a surface that is not
  in ``state`` also raises, since it would otherwise be silently dropped.

Every count is validated before anything is written, so a raise leaves ``state``
exactly as it was.
"""

from __future__ import annotations

FAILED_LABEL = "FAILED"


def _check_count(surface: str, value) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            f"count for {surface!r} must be an int or None, "
            f"got {type(value).__name__}"
        )
    if value < 0:
        raise ValueError(f"count for {surface!r} must be >= 0, got {value}")


def commit_heartbeats(state: dict, counts: dict, now: str) -> dict:
    """Bump ``last_checked`` for surfaces that reported an int count; hold the rest.

    ``state`` maps surface name -> per-surface dict. ``counts`` maps the same
    names to an int (items fetched this run) or ``None`` (fetch failed). ``now``
    is the timestamp string written into bumped surfaces.

    Returns ``{"bumped": [...], "held": [...], "line": "..."}``, where ``line`` is
    a one-line run summary in state order, e.g.
    ``inbox: muninns-inbox=3 bluesky=0 bluesky-dms=FAILED flight-log-comments=1``.

    Raises ValueError when a surface in ``state`` has no entry in ``counts``, when
    ``counts`` names a surface that is not in ``state``, or when a count is
    negative. Raises TypeError when a count is not an int or None (bool
    included), or when ``state``, ``counts`` or a surface entry is not a dict.
    Nothing is mutated on a raise.
    """
    if not isinstance(state, dict):
        raise TypeError("state must be a dict")
    if not isinstance(counts, dict):
        raise TypeError("counts must be a dict")
    if not isinstance(now, str) or not now:
        raise ValueError("now must be a non-empty timestamp string")

    missing = [s for s in state if s not in counts]
    if missing:
        raise ValueError(
            "no count reported for surface(s): " + ", ".join(map(str, missing))
        )
    unknown = [s for s in counts if s not in state]
    if unknown:
        raise ValueError(
            "count given for surface(s) not in state: " + ", ".join(map(str, unknown))
        )

    for surface, entry in state.items():
        if not isinstance(entry, dict):
            raise TypeError(f"state[{surface!r}] must be a dict")
        _check_count(surface, counts[surface])

    bumped: list[str] = []
    held: list[str] = []
    parts: list[str] = []
    for surface, entry in state.items():
        value = counts[surface]
        if value is None:
            held.append(surface)
            parts.append(f"{surface}={FAILED_LABEL}")
        else:
            entry["last_checked"] = now
            bumped.append(surface)
            parts.append(f"{surface}={value}")

    return {"bumped": bumped, "held": held, "line": "inbox: " + " ".join(parts)}
