"""Tests for muninn_utils.inbox_heartbeat.

The invariant under test: a surface's watermark moves only when that surface
reported an int count. A missing report, a bad count, or a raise must never
leave the watermark moved, and a raise must never leave state half-written.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from muninn_utils.inbox_heartbeat import commit_heartbeats

NOW = "2026-10-08T09:00:00Z"
OLD = "2026-10-07T21:00:00Z"


def fresh_state():
    return {
        "muninns-inbox": {"last_checked": OLD},
        "bluesky": {"last_checked": OLD},
        "bluesky-dms": {"last_checked": OLD},
        "flight-log-comments": {"last_checked": OLD},
    }


def test_bump_and_hold_mix():
    state = fresh_state()
    counts = {"muninns-inbox": 3, "bluesky": 0, "bluesky-dms": None, "flight-log-comments": 1}

    report = commit_heartbeats(state, counts, NOW)

    assert state["muninns-inbox"]["last_checked"] == NOW
    assert state["bluesky"]["last_checked"] == NOW  # zero is a real empty result
    assert state["bluesky-dms"]["last_checked"] == OLD  # failed fetch holds
    assert state["flight-log-comments"]["last_checked"] == NOW
    assert report["bumped"] == ["muninns-inbox", "bluesky", "flight-log-comments"]
    assert report["held"] == ["bluesky-dms"]
    assert report["line"] == (
        "inbox: muninns-inbox=3 bluesky=0 bluesky-dms=FAILED flight-log-comments=1"
    )


def test_all_none_bumps_nothing():
    state = fresh_state()
    before = copy.deepcopy(state)
    counts = {s: None for s in state}

    report = commit_heartbeats(state, counts, NOW)

    assert state == before
    assert report["bumped"] == []
    assert report["held"] == list(state)


def test_all_zero_bumps_everything():
    state = fresh_state()
    counts = {s: 0 for s in state}

    report = commit_heartbeats(state, counts, NOW)

    assert all(entry["last_checked"] == NOW for entry in state.values())
    assert report["held"] == []


def test_surface_added_without_last_checked_gets_one():
    state = {"bluesky": {}}
    commit_heartbeats(state, {"bluesky": 2}, NOW)
    assert state == {"bluesky": {"last_checked": NOW}}


def test_missing_surface_raises_and_state_untouched():
    state = fresh_state()
    before = copy.deepcopy(state)
    counts = {"muninns-inbox": 3, "bluesky": 0, "bluesky-dms": 0}  # no flight-log-comments

    with pytest.raises(ValueError, match="flight-log-comments"):
        commit_heartbeats(state, counts, NOW)

    assert state == before


def test_count_for_unknown_surface_raises_and_state_untouched():
    state = fresh_state()
    before = copy.deepcopy(state)
    counts = {s: 1 for s in state}
    counts["bluesky-dm"] = 1  # typo: would otherwise be silently dropped

    with pytest.raises(ValueError, match="bluesky-dm"):
        commit_heartbeats(state, counts, NOW)

    assert state == before


@pytest.mark.parametrize(
    ("bad", "error"),
    [("3", TypeError), ("", TypeError), (1.0, TypeError), (0.0, TypeError),
     (True, TypeError), (False, TypeError), ([], TypeError), ({}, TypeError),
     (-1, ValueError)],
)
def test_bad_count_types_raise_and_state_untouched(bad, error):
    state = fresh_state()
    before = copy.deepcopy(state)
    # Put the bad value last, so a naive loop would have bumped the earlier
    # surfaces before hitting it.
    counts = {"muninns-inbox": 3, "bluesky": 0, "bluesky-dms": None, "flight-log-comments": bad}

    with pytest.raises(error):
        commit_heartbeats(state, counts, NOW)

    assert state == before


def test_non_dict_surface_entry_raises_and_state_untouched():
    state = {"bluesky": {"last_checked": OLD}, "broken": "not-a-dict"}
    before = copy.deepcopy(state)

    with pytest.raises(TypeError, match="broken"):
        commit_heartbeats(state, {"bluesky": 1, "broken": 1}, NOW)

    assert state == before


def test_empty_timestamp_raises_and_state_untouched():
    state = fresh_state()
    before = copy.deepcopy(state)
    with pytest.raises(ValueError):
        commit_heartbeats(state, {s: 1 for s in state}, "")
    assert state == before


def test_non_dict_arguments_raise_type_error():
    with pytest.raises(TypeError):
        commit_heartbeats(None, {}, NOW)
    with pytest.raises(TypeError):
        commit_heartbeats({}, None, NOW)
