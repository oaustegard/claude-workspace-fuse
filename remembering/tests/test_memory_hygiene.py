"""Tests for tier-1 memory-hygiene changes (issues #54, #55, #56).

Covers:
- remember() idempotency window (#54) — same (summary, type) within the window
  returns the prior id instead of creating a duplicate row.
- curate() surfaces TF-IDF near-duplicates (#54) — strategy 3 the docstring
  has advertised since v5.1.0 but the code did not implement.
- prune_by_age() tag filter (#56) — restrict prune to memories whose tag list
  contains all the given tags (used to scope SLEEP/FLY session-log pruning).
- zeitgeist.md no longer persists skip telemetry as a memory (#55) — the
  policy file is the source of truth; this test asserts the bad pattern is
  gone and no remember() call remains in the skip branch.
"""

import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── #54 — remember() idempotency window ──

def test_remember_idempotency_returns_prior_id_within_window():
    """Within idempotency_window, a duplicate (summary, type) returns the prior id."""
    from scripts.memory import remember

    prior_id = "00000000-0000-0000-0000-000000000001"

    with patch("scripts.memory._exec") as mock_exec:
        # First call (idempotency probe) returns the prior memory; no write should follow.
        mock_exec.return_value = [{"id": prior_id}]

        result = remember("Identical summary text", "world", tags=["test"])

        assert str(result) == prior_id, f"Expected prior id, got {result!r}"
        # Only one _exec call — the idempotency probe. No INSERT.
        assert mock_exec.call_count == 1, \
            f"Expected 1 _exec (probe only), got {mock_exec.call_count}"
        probe_sql = mock_exec.call_args_list[0][0][0]
        assert "SELECT id FROM memories" in probe_sql, "First call must be the probe"

    print("PASS: remember() returns prior id within idempotency window")


def test_remember_idempotency_disabled_when_zero():
    """idempotency_window=0 disables the probe and always writes."""
    from scripts.memory import remember

    with patch("scripts.memory._exec") as mock_exec, \
         patch("scripts.memory._write_memory") as mock_write, \
         patch("scripts.memory.config_get", return_value=None), \
         patch("scripts.memory.config_set"):
        result = remember("Some summary", "world", idempotency_window=0)
        # Probe must not have run; _write_memory should have been called once.
        assert mock_exec.call_count == 0, \
            f"Probe should be skipped, but _exec called {mock_exec.call_count}x"
        assert mock_write.call_count == 1, "Write must run when probe is disabled"
        assert str(result) and len(str(result)) == 36, "Expected a fresh UUID"

    print("PASS: remember() idempotency_window=0 disables the probe")


def test_remember_idempotency_writes_when_no_prior():
    """When the probe finds nothing, a fresh write proceeds."""
    from scripts.memory import remember

    with patch("scripts.memory._exec", return_value=[]) as mock_exec, \
         patch("scripts.memory._write_memory") as mock_write, \
         patch("scripts.memory.config_get", return_value=None), \
         patch("scripts.memory.config_set"):
        result = remember("Novel summary", "world")
        # Probe ran, returned empty, then write proceeded.
        assert mock_exec.call_count == 1
        assert mock_write.call_count == 1
        # Fresh UUID, not a probed id
        assert len(str(result)) == 36

    print("PASS: remember() writes when idempotency probe returns no match")


def test_remember_idempotency_skipped_for_async_writes():
    """Async writes (sync=False) skip the probe — in-flight prior writes can't be seen."""
    import time as time_mod
    from scripts.memory import remember

    # Mock _write_memory so the background thread is a no-op (no Turso reach).
    with patch("scripts.memory._exec") as mock_exec, \
         patch("scripts.memory._write_memory"), \
         patch("scripts.memory.config_get", return_value=None), \
         patch("scripts.memory.config_set"):
        result = remember("Async summary", "world", sync=False)
        # Give the background thread a moment to finish; it must not have probed.
        time_mod.sleep(0.05)
        # The probe is a SELECT against memories. No call to _exec should have
        # happened on the async path (probe skipped; _write_memory is mocked).
        select_calls = [c for c in mock_exec.call_args_list
                        if "SELECT id FROM memories" in c[0][0]]
        assert not select_calls, \
            f"Async path must not run the idempotency probe; got: {select_calls}"
        assert len(str(result)) == 36

    print("PASS: remember() skips idempotency probe on sync=False")


def test_remember_idempotency_failure_falls_through_to_write():
    """If the probe query itself fails, a normal write still proceeds."""
    from scripts.memory import remember

    with patch("scripts.memory._exec", side_effect=RuntimeError("turso down")) as mock_exec, \
         patch("scripts.memory._write_memory") as mock_write, \
         patch("scripts.memory.config_get", return_value=None), \
         patch("scripts.memory.config_set"):
        result = remember("Resilient summary", "world")
        assert mock_exec.call_count == 1, "Probe was attempted"
        assert mock_write.call_count == 1, "Write proceeds despite probe failure"
        assert len(str(result)) == 36

    print("PASS: remember() falls through to write on probe exception")


# ── #54 — curate() surfaces lexical duplicates via MemoryIndex ──

def test_curate_surfaces_duplicates_from_memory_index():
    """curate() calls MemoryIndex.duplicates() and exposes the result."""
    from scripts import memory as memory_mod

    fake_pairs = [
        {"id_a": "aaa", "id_b": "bbb", "score": 0.99,
         "type_a": "world", "type_b": "world",
         "preview_a": "Identical fact", "preview_b": "Identical fact"},
    ]

    fake_index = MagicMock()
    fake_index.build.return_value = fake_index
    fake_index.duplicates.return_value = fake_pairs

    fake_module = MagicMock()
    fake_module.MemoryIndex.return_value = fake_index

    # consolidate() and the stale SELECT both hit _exec; return empty.
    with patch("scripts.memory._exec", return_value=[]), \
         patch.dict("sys.modules", {"muninn_utils.memory_tfidf": fake_module}):
        result = memory_mod.curate(dry_run=True)

    assert "duplicates" in result, "curate() must surface a duplicates key"
    assert result["duplicates"] == fake_pairs, "duplicates payload must round-trip"
    fake_index.build.assert_called_once()
    fake_index.duplicates.assert_called_once()
    # Pair count should land in a recommendation so dry-run reports flag it.
    rec_blob = " ".join(result["recommendations"])
    assert "near-duplicate" in rec_blob.lower() or "duplicate" in rec_blob.lower(), \
        f"Recommendations should mention duplicates; got: {result['recommendations']}"

    print("PASS: curate() surfaces TF-IDF duplicate pairs")


def test_curate_does_not_auto_delete_duplicates_even_when_not_dry_run():
    """Per #54: surface dups, never auto-delete on similarity."""
    from scripts import memory as memory_mod

    fake_pairs = [
        {"id_a": "aaa", "id_b": "bbb", "score": 0.99,
         "type_a": "world", "type_b": "world",
         "preview_a": "x", "preview_b": "x"},
    ]
    fake_index = MagicMock()
    fake_index.build.return_value = fake_index
    fake_index.duplicates.return_value = fake_pairs
    fake_module = MagicMock()
    fake_module.MemoryIndex.return_value = fake_index

    with patch("scripts.memory._exec", return_value=[]), \
         patch("scripts.memory.forget") as mock_forget, \
         patch("scripts.memory.reprioritize") as mock_reprioritize, \
         patch.dict("sys.modules", {"muninn_utils.memory_tfidf": fake_module}):
        result = memory_mod.curate(dry_run=False)

    assert mock_forget.call_count == 0, \
        f"curate() must not forget() duplicates, but called forget {mock_forget.call_count}x"
    # reprioritize is allowed for stale demotion, but we passed no stale memories,
    # so it should also be zero here.
    assert mock_reprioritize.call_count == 0
    assert result["duplicates"] == fake_pairs

    print("PASS: curate() never auto-deletes near-duplicates")


def test_curate_handles_memory_index_failure_gracefully():
    """If MemoryIndex isn't importable (partial install), curate still returns."""
    from scripts import memory as memory_mod

    # No fake module installed → import will fail inside curate(); it must report
    # via a recommendation rather than raise.
    with patch("scripts.memory._exec", return_value=[]), \
         patch.dict("sys.modules", {"muninn_utils.memory_tfidf": None}):
        # The patch above replaces the module with None so import resolves to None;
        # accessing MemoryIndex on it raises AttributeError, which curate() catches.
        result = memory_mod.curate(dry_run=True)

    assert result["duplicates"] == []
    rec_blob = " ".join(result["recommendations"]).lower()
    assert "duplicate scan failed" in rec_blob, \
        f"Failure must surface in recommendations; got: {result['recommendations']}"

    print("PASS: curate() degrades gracefully when MemoryIndex is unavailable")


# ── #56 — prune_by_age tag filter ──

def test_prune_by_age_adds_tag_clauses_to_where():
    """tags=[...] must add LIKE clauses to the WHERE so prune is scoped."""
    from scripts.memory import prune_by_age

    with patch("scripts.memory._exec", return_value=[]) as mock_exec, \
         patch("scripts.memory.forget") as mock_forget:
        result = prune_by_age(older_than_days=60, priority_floor=0,
                              tags=['session-log'], dry_run=True)

    assert mock_exec.call_count == 1
    sql, params = mock_exec.call_args[0]
    assert "tags LIKE" in sql, f"tag filter not wired into SQL: {sql}"
    # The LIKE pattern wraps the tag in quotes (JSON-array form).
    assert any('"session-log"' in str(p) for p in params), \
        f"Tag pattern not present in params: {params}"
    assert mock_forget.call_count == 0  # dry_run
    assert result["count"] == 0
    assert "session-log" in result["criteria"]

    print("PASS: prune_by_age tag filter adds LIKE clause + records in criteria")


def test_prune_by_age_without_tags_unchanged():
    """tags=None preserves the legacy single-clause SQL behavior."""
    from scripts.memory import prune_by_age

    with patch("scripts.memory._exec", return_value=[]) as mock_exec:
        prune_by_age(older_than_days=30, priority_floor=-1, dry_run=True)

    sql, params = mock_exec.call_args[0]
    assert "tags LIKE" not in sql, "No tag clause should be added when tags=None"
    assert len(params) == 2, f"Only cutoff + priority params expected, got {params}"

    print("PASS: prune_by_age omits tag clauses when tags=None")


def test_prune_by_age_multiple_tags_requires_all():
    """Multiple tags create multiple LIKE clauses ANDed together."""
    from scripts.memory import prune_by_age

    with patch("scripts.memory._exec", return_value=[]) as mock_exec:
        prune_by_age(older_than_days=60, tags=['session-log', 'fly'], dry_run=True)

    sql, _ = mock_exec.call_args[0]
    assert sql.count("tags LIKE") == 2, \
        f"Expected 2 tag LIKEs, got: {sql}"

    print("PASS: prune_by_age ANDs multiple tag clauses")


# ── #55 — zeitgeist skip path no longer persists telemetry ──

def test_zeitgeist_task_does_not_remember_skips():
    """The skip branch in zeitgeist.md must not call remember()."""
    import re

    task_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts", "tasks", "zeitgeist.md"
    )
    with open(task_path) as f:
        text = f.read()

    # Locate the floor-skip block.
    skip_block = re.search(
        r"if days is not None and days < MIN_DAYS_BETWEEN_RUNS:(.+?)```",
        text, re.DOTALL
    )
    assert skip_block, "Could not locate the floor-skip block in zeitgeist.md"
    body = skip_block.group(1)

    assert "remember(" not in body, \
        "Skip branch must not call remember() — that's exactly the pollution #55 fixed"
    assert "type='ops'" not in body and 'type="ops"' not in body, \
        "Skip branch must not reference invalid type='ops'"
    assert "return" in body, "Skip branch must still exit the task"

    print("PASS: zeitgeist.md skip branch persists no telemetry")


# ── Run all tests ──

if __name__ == "__main__":
    tests = [
        # #54 — idempotency
        test_remember_idempotency_returns_prior_id_within_window,
        test_remember_idempotency_disabled_when_zero,
        test_remember_idempotency_writes_when_no_prior,
        test_remember_idempotency_skipped_for_async_writes,
        test_remember_idempotency_failure_falls_through_to_write,
        # #54 — curate dedup
        test_curate_surfaces_duplicates_from_memory_index,
        test_curate_does_not_auto_delete_duplicates_even_when_not_dry_run,
        test_curate_handles_memory_index_failure_gracefully,
        # #56 — prune_by_age tag filter
        test_prune_by_age_adds_tag_clauses_to_where,
        test_prune_by_age_without_tags_unchanged,
        test_prune_by_age_multiple_tags_requires_all,
        # #55 — zeitgeist skip telemetry
        test_zeitgeist_task_does_not_remember_skips,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test_fn.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed:
        sys.exit(1)
