"""Tests for perch_publish.list_flight_logs and format_flight_window.

Regression for the fly routine's STEP 0 diversity check: sessions built the
7-log window from recall() and got short, unsorted, or stale windows, then
declared a domain "cold". list_flight_logs must ask GitHub for the category
directly and must raise rather than hand back a short window. gh_proxy.graphql
is mocked; no network.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from muninn_utils import gh_proxy
from muninn_utils import perch_publish as pp


def node(number, created):
    return {
        "number": number,
        "title": f"Fly {number}",
        "createdAt": created,
        "url": f"https://github.com/oaustegard/muninn.austegard.com/discussions/{number}",
    }


def page(nodes, total):
    return {"repository": {"discussions": {"totalCount": total, "nodes": nodes}}}


@pytest.fixture
def gql(monkeypatch):
    state = {"calls": [], "data": None, "error": None}

    def fake(query, variables=None, **kwargs):
        state["calls"].append((query, variables))
        if state["error"] is not None:
            raise state["error"]
        return state["data"]

    monkeypatch.setattr(gh_proxy, "graphql", fake)
    return state


# ── list_flight_logs ─────────────────────────────────────────────────────────

def test_returns_newest_first_with_field_mapping(gql):
    gql["data"] = page(
        [node(412, "2026-10-07T09:00:00Z"),
         node(410, "2026-10-05T18:30:00Z"),
         node(409, "2026-10-01T06:00:00Z")],
        total=3,
    )
    logs = pp.list_flight_logs(n=3)
    assert logs == [
        {"number": 412, "title": "Fly 412", "created_at": "2026-10-07T09:00:00Z",
         "url": "https://github.com/oaustegard/muninn.austegard.com/discussions/412"},
        {"number": 410, "title": "Fly 410", "created_at": "2026-10-05T18:30:00Z",
         "url": "https://github.com/oaustegard/muninn.austegard.com/discussions/410"},
        {"number": 409, "title": "Fly 409", "created_at": "2026-10-01T06:00:00Z",
         "url": "https://github.com/oaustegard/muninn.austegard.com/discussions/409"},
    ]
    assert [log["number"] for log in logs] == [412, 410, 409]


def test_query_pins_mac_repo_category_order_and_window(gql):
    gql["data"] = page([node(1, "2026-10-07T00:00:00Z")], total=1)
    pp.list_flight_logs()
    assert len(gql["calls"]) == 1
    query, variables = gql["calls"][0]
    assert "discussions(first: $n, categoryId: $cat," in query
    assert "orderBy: {field: CREATED_AT, direction: DESC}" in query
    assert variables == {
        "owner": "oaustegard",
        "name": "muninn.austegard.com",
        "n": 7,
        "cat": pp.FLIGHT_LOG_CATEGORY_ID,
    }


def test_short_window_raises_when_category_has_more(gql):
    gql["data"] = page(
        [node(n, "2026-10-07T00:00:00Z") for n in range(5)], total=9)
    with pytest.raises(RuntimeError, match="short"):
        pp.list_flight_logs(n=7)


def test_fewer_than_n_is_fine_when_category_is_small(gql):
    gql["data"] = page(
        [node(2, "2026-10-07T00:00:00Z"), node(1, "2026-10-01T00:00:00Z")], total=2)
    logs = pp.list_flight_logs(n=7)
    assert [log["number"] for log in logs] == [2, 1]


def test_graphql_failure_propagates_without_empty_fallback(gql):
    gql["error"] = RuntimeError("graphql errors: rate limited")
    with pytest.raises(RuntimeError, match="rate limited"):
        pp.list_flight_logs()


def test_missing_repository_raises(gql):
    gql["data"] = {"repository": None}
    with pytest.raises(RuntimeError, match="not found"):
        pp.list_flight_logs()


@pytest.mark.parametrize("n", [0, 101])
def test_window_size_out_of_range_rejected_before_any_call(gql, n):
    with pytest.raises(ValueError):
        pp.list_flight_logs(n=n)
    assert gql["calls"] == []


# ── format_flight_window ─────────────────────────────────────────────────────

def test_format_header_and_lines_newest_first():
    logs = [
        {"number": 412, "title": "Dream review", "created_at": "2026-10-07T09:00:00Z", "url": "u"},
        {"number": 409, "title": "Tokenizer drift", "created_at": "2026-10-01T06:00:00Z", "url": "u"},
    ]
    assert pp.format_flight_window(logs) == (
        "2 flight logs, 2026-10-01 to 2026-10-07 (UTC), newest first\n"
        "2026-10-07  #412  Dream review\n"
        "2026-10-01  #409  Tokenizer drift"
    )


def test_format_converts_offset_timestamps_to_utc_date():
    # 23:30 on Oct 1 at UTC-2 is 01:30 UTC on Oct 2; the line must say Oct 2.
    logs = [{"number": 7, "title": "Late", "created_at": "2026-10-01T23:30:00-02:00", "url": "u"}]
    out = pp.format_flight_window(logs)
    assert out.splitlines()[1] == "2026-10-02  #7  Late"
    assert out.splitlines()[0] == "1 flight logs, 2026-10-02 to 2026-10-02 (UTC), newest first"


def test_format_empty_window_is_explicit():
    assert pp.format_flight_window([]) == "0 flight logs in the Flight Log category"
