"""Tests for the recall cap signal and count() (date: 2026-10-08).

A recall() that returns exactly n rows is a lower bound on the store, not a
total. These tests pin:
- MemoryResultList.capped / __repr__ for capped, uncapped, empty and no-limit
  results (result.py).
- recall(), recall_since(), recall_between() set limit on the list they return,
  and raw=True keeps returning a plain list (memory.py).
- count(): exact COUNT(*) SQL and params, tag any-of vs all-of matching, and
  None (never 0) on failure (memory.py).

All I/O is mocked: no live Turso, no network.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.result import MemoryResultList, wrap_results


def _rows(k):
    """k minimal memory dicts, shaped like Turso rows."""
    return [
        {
            'id': f'00000000-0000-0000-0000-{i:012d}',
            'type': 'world',
            'summary': f'memory {i}',
            'created_at': '2026-01-01T00:00:00Z',
            'tags': [],
        }
        for i in range(k)
    ]


# ── MemoryResultList: capped and repr ──

def test_capped_when_len_reaches_limit():
    results = MemoryResultList(_rows(500), limit=500)
    assert results.capped is True
    assert repr(results) == (
        "MemoryResultList([500 memories, CAPPED at n=500: "
        "more may exist, use count()])"
    )


def test_not_capped_when_below_limit():
    results = MemoryResultList(_rows(3), limit=500)
    assert results.capped is False
    assert repr(results) == "MemoryResultList([3 memories])"


def test_not_capped_without_limit_even_when_large():
    results = MemoryResultList(_rows(40))
    assert results.limit is None
    assert results.capped is False
    assert repr(results) == "MemoryResultList([40 memories])"


def test_empty_without_limit_keeps_legacy_repr():
    results = MemoryResultList()
    assert results.limit is None
    assert results.capped is False
    assert repr(results) == "MemoryResultList([])"


def test_empty_under_limit_is_not_capped():
    results = MemoryResultList(limit=10)
    assert results.capped is False
    assert repr(results) == "MemoryResultList([])"


def test_capped_is_bool_and_tracks_length_live():
    results = MemoryResultList(_rows(1), limit=2)
    assert results.capped is False
    results.append(_rows(1)[0])
    assert results.capped is True


def test_stays_a_list_subclass():
    results = MemoryResultList(_rows(2), limit=2)
    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]['summary'] == 'memory 0'
    assert [m['summary'] for m in results] == ['memory 0', 'memory 1']


def test_wrap_results_records_limit():
    wrapped = wrap_results(_rows(2), limit=2)
    assert isinstance(wrapped, MemoryResultList)
    assert wrapped.limit == 2
    assert wrapped.capped is True
    assert repr(wrapped).startswith("MemoryResultList([2 memories, CAPPED at n=2:")


def test_wrap_results_default_has_no_limit():
    wrapped = wrap_results(_rows(2))
    assert wrapped.limit is None
    assert wrapped.capped is False


# ── recall() wiring ──

def test_recall_fetch_all_at_cap_is_capped():
    from scripts import memory
    with patch.object(memory, '_query', return_value=_rows(2)), \
         patch.object(memory, '_update_access_tracking'):
        res = memory.recall(fetch_all=True, n=2)
    assert res.limit == 2
    assert res.capped is True
    assert repr(res) == (
        "MemoryResultList([2 memories, CAPPED at n=2: "
        "more may exist, use count()])"
    )


def test_recall_fetch_all_below_cap_is_not_capped():
    from scripts import memory
    with patch.object(memory, '_query', return_value=_rows(2)), \
         patch.object(memory, '_update_access_tracking'):
        res = memory.recall(fetch_all=True, n=5)
    assert res.limit == 5
    assert res.capped is False
    assert repr(res) == "MemoryResultList([2 memories])"


def test_recall_search_path_records_limit():
    from scripts import memory
    with patch.object(memory, '_fts5_search', return_value=_rows(2)), \
         patch.object(memory, '_update_access_tracking'):
        res = memory.recall('anything', n=2, expansion_threshold=0)
    assert res.limit == 2
    assert res.capped is True


def test_recall_raw_returns_plain_list_without_limit():
    from scripts import memory
    with patch.object(memory, '_query', return_value=_rows(2)), \
         patch.object(memory, '_update_access_tracking'):
        res = memory.recall(fetch_all=True, n=2, raw=True)
    assert type(res) is list
    assert not hasattr(res, 'capped')
    assert not hasattr(res, 'limit')


def test_recall_since_records_limit():
    from scripts import memory
    with patch.object(memory, '_exec', return_value=_rows(2)), \
         patch.object(memory, '_update_access_tracking'):
        res = memory.recall_since('2026-01-01T00:00:00Z', n=2)
    assert res.limit == 2
    assert res.capped is True


def test_recall_between_records_limit():
    from scripts import memory
    with patch.object(memory, '_exec', return_value=_rows(2)), \
         patch.object(memory, '_update_access_tracking'):
        res = memory.recall_between('2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z', n=5)
    assert res.limit == 5
    assert res.capped is False


def test_recall_since_raw_is_plain_list():
    from scripts import memory
    with patch.object(memory, '_exec', return_value=_rows(2)), \
         patch.object(memory, '_update_access_tracking'):
        res = memory.recall_since('2026-01-01T00:00:00Z', n=2, raw=True)
    assert type(res) is list


# ── count() ──

def test_count_no_filters_sql_and_params():
    from scripts.memory import count
    with patch("scripts.memory._exec", return_value=[{'n': '7'}]) as mock_exec:
        total = count()
    assert total == 7
    assert isinstance(total, int)
    sql, params = mock_exec.call_args[0]
    assert sql == (
        "SELECT COUNT(*) AS n FROM memories "
        "WHERE deleted_at IS NULL AND is_superseded = 0"
    )
    assert params == []
    assert "LIMIT" not in sql


def test_count_tags_is_any_of():
    from scripts.memory import count
    with patch("scripts.memory._exec", return_value=[{'n': '3'}]) as mock_exec:
        assert count(tags=['alpha', 'beta']) == 3
    sql, params = mock_exec.call_args[0]
    assert sql == (
        "SELECT COUNT(*) AS n FROM memories "
        "WHERE deleted_at IS NULL AND is_superseded = 0 "
        "AND (tags LIKE ? ESCAPE '\\' OR tags LIKE ? ESCAPE '\\')"
    )
    assert params == ['%"alpha"%', '%"beta"%']


def test_count_tags_all_is_all_of():
    from scripts.memory import count
    with patch("scripts.memory._exec", return_value=[{'n': '2'}]) as mock_exec:
        assert count(tags_all=['alpha', 'beta']) == 2
    sql, params = mock_exec.call_args[0]
    assert sql == (
        "SELECT COUNT(*) AS n FROM memories "
        "WHERE deleted_at IS NULL AND is_superseded = 0 "
        "AND tags LIKE ? ESCAPE '\\' AND tags LIKE ? ESCAPE '\\'"
    )
    assert params == ['%"alpha"%', '%"beta"%']


def test_count_escapes_like_wildcards_in_tags():
    from scripts.memory import count
    with patch("scripts.memory._exec", return_value=[{'n': '0'}]) as mock_exec:
        count(tags=['under_score', '100%'])
    _, params = mock_exec.call_args[0]
    assert params == ['%"under\\_score"%', '%"100\\%"%']


def test_count_empty_tag_lists_add_no_filter():
    from scripts.memory import count
    with patch("scripts.memory._exec", return_value=[{'n': '4'}]) as mock_exec:
        count(tags=[], tags_all=[])
    sql, params = mock_exec.call_args[0]
    assert "tags" not in sql
    assert params == []


def test_count_type_and_time_window_sql_and_params():
    from scripts.memory import count
    with patch("scripts.memory._exec", return_value=[{'n': '5'}]) as mock_exec:
        assert count(
            tags=['a'], tags_all=['b'], type='world',
            since='2026-01-01T00:00:00Z', until='2026-02-01T00:00:00Z',
        ) == 5
    sql, params = mock_exec.call_args[0]
    assert sql == (
        "SELECT COUNT(*) AS n FROM memories "
        "WHERE deleted_at IS NULL AND is_superseded = 0 "
        "AND (tags LIKE ? ESCAPE '\\') "
        "AND tags LIKE ? ESCAPE '\\' "
        "AND type = ? "
        "AND t >= ? AND t <= ?"
    )
    assert params == ['%"a"%', '%"b"%', 'world',
                      '2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z']


def test_count_normalizes_offset_timestamps_to_utc():
    from scripts.memory import count
    with patch("scripts.memory._exec", return_value=[{'n': '1'}]) as mock_exec:
        count(since='2026-01-01T02:00:00+02:00')
    _, params = mock_exec.call_args[0]
    assert params == ['2026-01-01T00:00:00Z']


def test_count_returns_none_when_query_raises():
    from scripts.memory import count
    with patch("scripts.memory._exec", side_effect=RuntimeError("HTTP 503")):
        assert count() is None


def test_count_returns_none_not_zero_on_empty_response():
    from scripts.memory import count
    with patch("scripts.memory._exec", return_value=[]):
        assert count() is None
