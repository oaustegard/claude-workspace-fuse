"""Migration: add superseded_by to memories and repair the lineage flags.

`superseded_by` names the memory that replaced a retired one, so a citation of
a superseded memory can be followed forward. supersede() writes it from
v5.x on; this recovers it for older rows from the signature supersede()
leaves, and clears is_superseded on live rows nothing replaced (see
scripts/integrity.py for both rules and the measurements behind them).

Usage:
    python add_superseded_by_column.py              # apply
    python add_superseded_by_column.py --status     # column state + pending repairs
    python add_superseded_by_column.py --dry-run    # print the plan, write nothing

Idempotent. boot() adds the column on its own and runs the repair when it
does, so this script is for diagnostics and for re-running the repair.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.integrity import ensure_superseded_by_column, repair  # noqa: E402
from scripts.turso import _exec, _init  # noqa: E402


def column_exists() -> bool:
    return any(r.get("name") == "superseded_by" for r in _exec("PRAGMA table_info(memories)"))


def _show(plan, limit=5):
    c = plan["counts"]
    print(f"  link supersessions:  {c['link']}")
    for orig, new in plan["link"][:limit]:
        print(f"    {orig[:8]} -> {new[:8]}")
    print(f"  unflag live rows:    {c['unflag']}")
    for mid in plan["unflag"][:limit]:
        print(f"    {mid[:8]}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--status", action="store_true")
    g.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    _init()

    exists = column_exists()
    print(f"superseded_by column exists: {exists}")
    if args.status or args.dry_run:
        if not exists:
            print("  (plan below assumes the column is added first)")
        _show(repair(write=False))
        return 0

    if ensure_superseded_by_column(_exec):
        print("Added superseded_by column")
    plan = repair(write=True)
    _show(plan)
    print("written" if plan["written"] else "nothing to write")
    return 0


if __name__ == "__main__":
    sys.exit(main())
