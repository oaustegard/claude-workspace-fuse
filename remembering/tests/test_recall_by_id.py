"""Tests for by-id retrieval: get() export, memory_get alias, recall(id=/ids=).

date: 2026-10-08. Sessions kept reaching for recall(id=...), recall(ids=[...]),
sql_query and memory_get, and each guess cost 3-12 turns, because the by-id
getter existed in memory.py but was never exported and recall() had no by-id
form. These tests pin the export, the alias, and the id/ids routing.

All I/O is mocked: _exec (Turso) and _resolve_memory_id (partial-id resolution).
No network, no credentials.
"""

import os
import sys
import warnings
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import (
    MemoryResult,
    MemoryResultList,
    get,
    memory_get,
    recall,
)

A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"
C = "33333333-3333-4333-8333-333333333333"
MISSING = "44444444-4444-4444-8444-444444444444"


def _row(mid, summary):
    return {
        "id": mid,
        "summary": summary,
        "type": "world",
        "tags": '["t"]',
        "priority": 0,
        "confidence": 1.0,
        "created_at": "2026-10-01T00:00:00Z",
        "updated_at": "2026-10-01T00:00:00Z",
        "deleted_at": None,
    }


STORE = {A: _row(A, "alpha"), B: _row(B, "bravo"), C: _row(C, "charlie")}


def _fake_exec(sql, params=None):
    """Answer only the by-id SELECT that get() issues; anything else is a bug here."""
    if sql.startswith("SELECT * FROM memories WHERE id = ?"):
        row = STORE.get(params[0])
        return [dict(row)] if row else []
    raise AssertionError(f"unexpected SQL in by-id test: {sql!r}")


def _patched():
    """Context managers: mocked Turso read, identity id resolution, no FTS path."""
    return (
        patch("scripts.memory._exec", side_effect=_fake_exec),
        patch("scripts.memory._resolve_memory_id", side_effect=lambda m: m),
    )


# ── export surface ──

def test_get_and_memory_get_are_exported():
    import scripts
    assert "get" in scripts.__all__
    assert "memory_get" in scripts.__all__
    assert memory_get is get, "memory_get must be the same callable as get"


def test_from_scripts_import_get_and_memory_get_works():
    from scripts import get as g
    from scripts import memory_get as mg
    assert callable(g) and callable(mg)


def test_get_returns_memory_result_for_full_id():
    p_exec, p_resolve = _patched()
    with p_exec, p_resolve:
        row = get(A)
    assert isinstance(row, MemoryResult)
    assert row["summary"] == "alpha"


def test_get_returns_none_for_unknown_full_id():
    p_exec, p_resolve = _patched()
    with p_exec, p_resolve:
        assert get(MISSING) is None


# ── recall(id=) ──

def test_recall_id_returns_one_item_memory_result_list():
    p_exec, p_resolve = _patched()
    with p_exec, p_resolve:
        out = recall(id=A)
    assert isinstance(out, MemoryResultList)
    assert len(out) == 1
    assert isinstance(out[0], MemoryResult)
    assert out[0]["summary"] == "alpha"


def test_recall_id_missing_returns_empty_list():
    p_exec, p_resolve = _patched()
    with p_exec, p_resolve:
        out = recall(id=MISSING)
    assert isinstance(out, MemoryResultList)
    assert len(out) == 0


def test_recall_id_raw_returns_plain_dicts():
    p_exec, p_resolve = _patched()
    with p_exec, p_resolve:
        out = recall(id=A, raw=True)
    assert isinstance(out, list) and not isinstance(out, MemoryResultList)
    assert out[0]["id"] == A


# ── recall(ids=[...]) ──

def test_recall_ids_preserves_given_order_and_skips_missing():
    p_exec, p_resolve = _patched()
    with p_exec, p_resolve:
        out = recall(ids=[C, MISSING, A])
    assert isinstance(out, MemoryResultList)
    assert [m["summary"] for m in out] == ["charlie", "alpha"]


def test_recall_ids_all_missing_returns_empty():
    p_exec, p_resolve = _patched()
    with p_exec, p_resolve:
        out = recall(ids=[MISSING])
    assert len(out) == 0


def test_recall_ids_empty_list_returns_empty_without_touching_turso():
    with patch("scripts.memory._exec", side_effect=AssertionError("must not query")) as ex:
        out = recall(ids=[])
    assert len(out) == 0
    ex.assert_not_called()


def test_recall_ids_raw_returns_plain_dicts_in_order():
    p_exec, p_resolve = _patched()
    with p_exec, p_resolve:
        out = recall(ids=[B, A], raw=True)
    assert [d["id"] for d in out] == [B, A]


def test_recall_ids_ignores_search_and_other_filters():
    """With id/ids set, search, tags, type and the rest are not applied."""
    with patch("scripts.memory._fts5_search", side_effect=AssertionError("search must not run")) as fts:
        p_exec, p_resolve = _patched()
        with p_exec, p_resolve:
            out = recall("nothing matches this", tags=["no-such-tag"], type="decision",
                         since="2100-01-01", ids=[A])
    fts.assert_not_called()
    assert [m["summary"] for m in out] == ["alpha"]


def test_recall_id_and_ids_together_raises():
    try:
        recall(id=A, ids=[B])
    except ValueError as e:
        assert "not both" in str(e)
        return
    raise AssertionError("expected ValueError when both id= and ids= are passed")


def test_recall_id_wrong_type_raises_typeerror():
    try:
        recall(id=5)
    except TypeError as e:
        assert "str" in str(e)
        return
    raise AssertionError("expected TypeError for non-str id=")


def test_recall_ids_bare_string_raises_typeerror():
    """A bare string is iterable; it must not be silently split into characters."""
    try:
        recall(ids=A)
    except TypeError as e:
        assert "list" in str(e)
        return
    raise AssertionError("expected TypeError for ids= given a bare string")


# ── alias translation (accept_aliases) ──

def test_recall_memory_id_alias_warns_and_translates():
    p_exec, p_resolve = _patched()
    with p_exec, p_resolve, warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = recall(memory_id=A)
    assert [m["summary"] for m in out] == ["alpha"]
    assert any(
        issubclass(w.category, DeprecationWarning) and "memory_id" in str(w.message)
        for w in caught
    ), "DeprecationWarning for memory_id not emitted"


def test_recall_memory_ids_alias_warns_and_translates():
    p_exec, p_resolve = _patched()
    with p_exec, p_resolve, warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = recall(memory_ids=[B, A])
    assert [m["summary"] for m in out] == ["bravo", "alpha"]
    assert any(
        issubclass(w.category, DeprecationWarning) and "memory_ids" in str(w.message)
        for w in caught
    )


def test_recall_canonical_id_kwarg_does_not_warn():
    p_exec, p_resolve = _patched()
    with p_exec, p_resolve, warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        recall(id=A)
    assert not [w for w in caught if issubclass(w.category, DeprecationWarning)]


if __name__ == "__main__":
    import inspect
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and inspect.isfunction(fn):
            try:
                fn()
                print(f"PASS: {name}")
            except Exception as e:  # noqa: BLE001 - the standalone runner reports every failure
                failed += 1
                print(f"FAIL: {name}: {e}")
    raise SystemExit(1 if failed else 0)
