"""Reversible migration: add a `source` write-provenance column to memories and config.

Stage 0 of the remote-MCP migration (docs/mcp-migration.md §5). Every write stamps
which writer produced it — `skill@5.12.0`, `mcp@0.1.0`, `muninnd@0.1.0` — so that
once a second writer exists, its rows are identifiable.

This ships ALONE, before any second writer, because the Stage 3 data rollback is::

    UPDATE memories SET deleted_at = <now>
    WHERE source LIKE 'mcp@%' AND created_at > <cutover>

and that is only bounded if provenance was already being written when the second
writer's first row landed. Nothing reads `source` yet.

Usage:
    python add_write_provenance_v1.py              # Apply migration
    python add_write_provenance_v1.py --status     # Column + backfill + coverage state
    python add_write_provenance_v1.py --dry-run    # Preview changes without applying
    python add_write_provenance_v1.py --backfill   # Re-stamp NULL rows (see caveat)
    python add_write_provenance_v1.py --rollback   # Drop columns (DESTRUCTIVE)

Idempotent: safe to run repeatedly. boot() also runs the ALTER + first backfill on
every boot via scripts.boot._ensure_write_provenance_schema(), so most deployments
never invoke this manually — it exists for diagnostics, the bake gate, and rollback.

BAKE GATE (Stage 0 exit criterion): --status must report zero NULL sources among
rows created after the migration timestamp, sustained for one week, before Stage 1
(green built read-only) begins.
"""

import argparse
import sys
from pathlib import Path

# Ensure remembering package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.provenance import PRE_PROVENANCE, write_source
from scripts.turso import _exec, _init

TABLES = ("memories", "config")


def column_exists(table: str) -> bool:
    """Return True if `source` is already a column of the given table."""
    rows = _exec(f"PRAGMA table_info({table})")
    return any(r.get("name") == "source" for r in rows)


def _count(sql: str, args=None) -> int:
    rows = _exec(sql, args) if args else _exec(sql)
    return int(rows[0].get("n", 0)) if rows else 0


def null_source_count(table: str) -> int:
    """Rows with no provenance stamp at all."""
    try:
        return _count(f"SELECT COUNT(*) AS n FROM {table} WHERE source IS NULL")
    except Exception:  # noqa: BLE001 - querying a column that may not exist yet
        return -1  # column absent


def source_breakdown(table: str):
    """(source, count) pairs, most common first."""
    try:
        return [
            (r.get("source"), r.get("n"))
            for r in _exec(
                f"SELECT source, COUNT(*) AS n FROM {table} "
                f"GROUP BY source ORDER BY n DESC"
            )
        ]
    except Exception:  # noqa: BLE001 - querying a column that may not exist yet
        return []


def status():
    """Print current migration state and the bake-gate measurement."""
    _init()
    print(f"current write_source(): {write_source()}\n")
    for table in TABLES:
        exists = column_exists(table)
        total = _count(f"SELECT COUNT(*) AS n FROM {table}")
        print(f"--- {table} ---")
        print(f"  source column exists: {exists}")
        print(f"  total rows:           {total}")
        if not exists:
            print()
            continue
        nulls = null_source_count(table)
        print(f"  NULL source:          {nulls}")
        for src, n in source_breakdown(table)[:8]:
            print(f"    {src!s:28} {n}")
        # The gate cares about rows written SINCE provenance landed. Pre-migration
        # rows carry the sentinel, so anything still NULL is a straggler writer.
        if nulls == 0:
            print("  GATE: no unstamped rows")
        else:
            print(f"  GATE: FAILING — {nulls} unstamped row(s); find the writer that skipped the stamp")
        print()


def apply(dry_run: bool = False):
    """Apply the migration: ALTER both tables, then backfill pre-existing rows."""
    _init()

    for table in TABLES:
        if column_exists(table):
            print(f"{table}: source column already exists — skipping ALTER")
            did_alter = False
        elif dry_run:
            print(f"[dry-run] would: ALTER TABLE {table} ADD COLUMN source TEXT")
            did_alter = True
        else:
            _exec(f"ALTER TABLE {table} ADD COLUMN source TEXT")
            print(f"{table}: added source column")
            did_alter = True

        if not did_alter:
            print(f"{table}: skipping backfill (column was already present)")
            continue

        if dry_run:
            total = _count(f"SELECT COUNT(*) AS n FROM {table}")
            print(f"[dry-run] would backfill {total} row(s) to {PRE_PROVENANCE!r}")
        else:
            # Every existing row was written by the Python skill — nothing else has
            # ever held write credentials. Stamping them with a real version would
            # assert a fact we cannot check, so they get the sentinel instead; it
            # keeps the cutover moment queryable, which is the point.
            _exec(
                f"UPDATE {table} SET source = ? WHERE source IS NULL",
                [PRE_PROVENANCE],
            )
            remaining = null_source_count(table)
            print(f"{table}: backfill complete ({remaining} NULL remaining)")


def backfill():
    """Re-stamp any NULL rows with the pre-provenance sentinel.

    CAVEAT: only run this deliberately. During the Stage 0 bake, a NULL source is
    the signal that some writer is skipping the stamp — papering over it with a
    backfill destroys the measurement the gate depends on. Diagnose first.
    """
    _init()
    for table in TABLES:
        if not column_exists(table):
            print(f"{table}: no source column — run without --backfill first")
            continue
        before = null_source_count(table)
        if before == 0:
            print(f"{table}: nothing to backfill")
            continue
        _exec(f"UPDATE {table} SET source = ? WHERE source IS NULL", [PRE_PROVENANCE])
        print(f"{table}: stamped {before} row(s) as {PRE_PROVENANCE}")


def rollback():
    """Drop the source columns. DESTRUCTIVE — provenance is unrecoverable after this.

    Safe with respect to the code: nothing READS `source` yet, and the INSERT sites
    that write it would start failing with 'no such column'. Roll the code back in
    the same commit, or re-run this migration immediately.
    """
    _init()

    print("ROLLBACK: this will drop `source` from memories and config.")
    print("The write paths stamp this column — roll back the code too, or every")
    print("remember()/config_set() will fail with 'no such column: source'.")
    if input("Type 'yes' to proceed: ").strip().lower() != "yes":
        print("Aborted.")
        return

    for table in TABLES:
        if column_exists(table):
            # SQLite supports DROP COLUMN since 3.35.0 (2021). Turso is modern.
            _exec(f"ALTER TABLE {table} DROP COLUMN source")
            print(f"{table}: dropped source column")

    print("Rollback complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true", help="Show migration + bake-gate state")
    group.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    group.add_argument("--backfill", action="store_true", help="Re-stamp NULL rows (read the caveat)")
    group.add_argument("--rollback", action="store_true", help="Drop the columns (DESTRUCTIVE)")
    args = parser.parse_args()

    if args.status:
        status()
    elif args.rollback:
        rollback()
    elif args.backfill:
        backfill()
    else:
        apply(dry_run=args.dry_run)
