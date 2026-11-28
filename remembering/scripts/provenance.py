"""Write provenance — which writer produced a row.

Stage 0 of the remote-MCP migration (docs/mcp-migration.md §5). Every INSERT into
`memories` and `config` stamps a `source` column identifying the writer, so that
once a second writer exists its rows are distinguishable from the skill's.

WHY THIS SHIPS BEFORE ANY SECOND WRITER EXISTS
----------------------------------------------
The migration plan's data rollback is::

    UPDATE memories SET deleted_at = <now>
    WHERE source LIKE 'mcp@%' AND created_at > <cutover>

That query is only *bounded and precise* if provenance was already being written
when the second writer's first row landed. Adding the column later means the rows
you most need to identify are exactly the ones you cannot. So this lands in blue,
alone, and bakes — nothing reads `source` yet.

FORMAT
------
``<writer>@<version>`` — e.g. ``skill@5.12.0``, ``mcp@0.1.0``, ``muninnd@0.1.0``.
Rows written before this migration are backfilled to ``skill@pre-provenance``:
they were all written by the Python skill (nothing else has ever had write
credentials), but stamping them with a real version would assert a fact we cannot
check. The sentinel keeps the cutover moment queryable, which is the whole point.

OVERRIDE
--------
Set ``MUNINN_WRITE_SOURCE`` to change the stamp without touching any call site::

    MUNINN_WRITE_SOURCE=mcp@0.1.0

That indirection is deliberate. When the remote MCP server runs this same code —
the Python path imports `remembering/scripts` unmodified whether it is in a
session container or behind an MCP endpoint — it sets the env var and every
INSERT site is already correct. No second code path, no per-site patch.
"""

import os
import re
from functools import lru_cache
from pathlib import Path

#: Env var that overrides the computed source. See module docstring.
SOURCE_ENV_VAR = "MUNINN_WRITE_SOURCE"

#: Writer name used when nothing overrides it.
DEFAULT_WRITER = "skill"

#: Fallback when SKILL.md can't be read (installed without it, permissions, etc).
#: Kept in sync with remembering/SKILL.md by the release process; the file read
#: below is authoritative when available so the two cannot silently diverge.
FALLBACK_VERSION = "5.12.0"

#: Stamp applied by the migration to rows that predate provenance.
PRE_PROVENANCE = "skill@pre-provenance"

_VERSION_RE = re.compile(r"^\s*version:\s*([0-9][^\s#]*)", re.MULTILINE)


@lru_cache(maxsize=1)
def skill_version() -> str:
    """Read the skill version from SKILL.md's frontmatter, cached per process.

    One small file read on first use, then memoised — `_write_memory` is on the
    hot path and must not touch the filesystem per call.
    """
    try:
        skill_md = Path(__file__).resolve().parent.parent / "SKILL.md"
        match = _VERSION_RE.search(skill_md.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    except Exception:  # noqa: BLE001, S110 - see below
        # Deliberately total. A version we cannot read is not a reason to fail a
        # write, and there is nowhere useful to log from this layer.
        pass
    return FALLBACK_VERSION


def write_source() -> str:
    """Return the provenance stamp for a write originating in this process.

    Never raises: provenance is metadata, and a failure to compute it must not
    fail the write it describes.
    """
    try:
        override = (os.environ.get(SOURCE_ENV_VAR) or "").strip()
        if override:
            return override
        return f"{DEFAULT_WRITER}@{skill_version()}"
    except Exception:  # noqa: BLE001 - metadata must never fail its own write
        return f"{DEFAULT_WRITER}@{FALLBACK_VERSION}"


def writer_of(source: str | None) -> str | None:
    """Split the writer out of a stamp: ``'mcp@0.1.0'`` -> ``'mcp'``.

    Returns None for a null/blank source (a pre-migration row, or a write that
    somehow escaped stamping — which is exactly what the Stage 0 bake gate looks
    for).
    """
    if not source:
        return None
    return source.split("@", 1)[0] or None
