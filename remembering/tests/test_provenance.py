"""Tests for write provenance (Stage 0 of the remote-MCP migration).

Offline: nothing here touches Turso. The stamp helper is pure, and the INSERT
wiring is asserted by reading the SQL text of the write sites — which is the
property that actually matters. A stamp that exists but is not threaded into
every INSERT is worse than no stamp, because the bake gate would read as green
while a writer quietly produced NULL-source rows.
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.provenance import (
    DEFAULT_WRITER,
    FALLBACK_VERSION,
    PRE_PROVENANCE,
    SOURCE_ENV_VAR,
    skill_version,
    write_source,
    writer_of,
)

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

_passed = 0
_failed = 0


def check(name, got, want):
    global _passed, _failed
    if got == want:
        _passed += 1
        print(f"OK  {name}")
    else:
        _failed += 1
        print(f"FAIL {name}\n  got:  {got!r}\n  want: {want!r}")


def check_true(name, got):
    check(name, bool(got), True)


# ---------------------------------------------------------------- the stamp

def test_default_shape():
    os.environ.pop(SOURCE_ENV_VAR, None)
    src = write_source()
    check_true("default source is writer@version", re.fullmatch(r"skill@[0-9][^\s]*", src))
    check("default writer is the skill", writer_of(src), DEFAULT_WRITER)


def test_env_override():
    os.environ[SOURCE_ENV_VAR] = "mcp@0.1.0"
    try:
        check("env var overrides the stamp", write_source(), "mcp@0.1.0")
        check("writer_of splits the override", writer_of(write_source()), "mcp")
    finally:
        os.environ.pop(SOURCE_ENV_VAR, None)


def test_blank_env_falls_back():
    os.environ[SOURCE_ENV_VAR] = "   "
    try:
        check("blank override is ignored", writer_of(write_source()), DEFAULT_WRITER)
    finally:
        os.environ.pop(SOURCE_ENV_VAR, None)


def test_version_matches_skill_md():
    """The helper reads SKILL.md so the constant cannot silently drift from it."""
    skill_md = (SCRIPTS.parent / "SKILL.md").read_text(encoding="utf-8")
    declared = re.search(r"^\s*version:\s*([0-9][^\s#]*)", skill_md, re.MULTILINE)
    check_true("SKILL.md declares a version", declared)
    if declared:
        check("skill_version() reads SKILL.md", skill_version(), declared.group(1))
        check(
            "FALLBACK_VERSION is in sync with SKILL.md",
            FALLBACK_VERSION,
            declared.group(1),
        )


def test_writer_of_edges():
    check("writer_of(None) is None", writer_of(None), None)
    check("writer_of('') is None", writer_of(""), None)
    check("writer_of with no @ returns the whole string", writer_of("skill"), "skill")
    check("pre-provenance sentinel reads as skill", writer_of(PRE_PROVENANCE), "skill")


# ---------------------------------------------------------------- the wiring

#: Every site that INSERTs a row which must carry provenance.
WRITE_SITES = [
    ("memory.py", "INSERT INTO memories", 3),
    ("config.py", "INSERT OR REPLACE INTO config", 1),
    ("task.py", "INSERT OR REPLACE INTO config", 1),
]


def test_every_insert_site_is_stamped():
    """Guards the failure mode the bake gate cannot see: an unstamped INSERT.

    If someone adds a new INSERT without threading write_source() through, the
    counts here stop matching and this fails — long before a NULL-source row
    reaches production and quietly invalidates the Stage 3 rollback query.
    """
    for filename, insert_sql, expected in WRITE_SITES:
        text = (SCRIPTS / filename).read_text(encoding="utf-8")
        found = text.count(insert_sql)
        check(f"{filename}: {expected} '{insert_sql}' site(s)", found, expected)

        # Every one of those INSERTs must name the source column...
        stmts = [s for s in text.split(insert_sql)[1:]]
        for i, stmt in enumerate(stmts):
            head = stmt[:400]
            check_true(f"{filename}: INSERT #{i + 1} names the source column", "source" in head)

        # ...and the file must call the stamp helper once per site.
        check(f"{filename}: write_source() called {expected}x", text.count("write_source()"), expected)
        check_true(f"{filename}: imports write_source", "from .provenance import write_source" in text)


def test_boot_ensures_the_column():
    boot = (SCRIPTS / "boot.py").read_text(encoding="utf-8")
    check_true("boot defines the ensure hook", "def _ensure_write_provenance_schema()" in boot)
    # Defined AND called — a hook nobody calls is the classic silent no-op.
    # `def name():` also contains `name()`, so count only non-def occurrences.
    calls = sum(
        1
        for line in boot.splitlines()
        if "_ensure_write_provenance_schema()" in line and not line.lstrip().startswith("def ")
    )
    check("boot calls the ensure hook", calls, 1)
    check_true(
        "ensure hook alters both tables",
        'for table in ("memories", "config")' in boot,
    )


def test_migration_exists_and_is_reversible():
    mig = (SCRIPTS / "migrations" / "add_write_provenance_v1.py").read_text(encoding="utf-8")
    for flag in ("--status", "--dry-run", "--rollback", "--backfill"):
        check_true(f"migration supports {flag}", flag in mig)
    check_true("migration drops the column on rollback", "DROP COLUMN source" in mig)


if __name__ == "__main__":
    for fn in sorted(
        (v for k, v in list(globals().items()) if k.startswith("test_")),
        key=lambda f: f.__code__.co_firstlineno,
    ):
        fn()
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)
