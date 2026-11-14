"""Tests for volatility.py: read-time staleness of volatile memory claims.

Pure unit tests, no network. The cases live in volatility_fixtures.json, which
muninn-mcp's src/volatility.test.ts runs too, so the two classifiers cannot
drift apart silently.

Run from repo root:
    python3 -m pytest remembering/tests/test_volatility.py
"""

import json
import os
import sys
from datetime import datetime

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from scripts import volatility as v

with open(os.path.join(HERE, "volatility_fixtures.json")) as f:
    CASES = json.load(f)["cases"]


def _now(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_fixture(case):
    got = v.assess(case["text"], case["created_at"], _now(case["now"]), tags=case["tags"])
    if case.get("skip") or not (case["kinds"] or case["refs"]):
        assert got is None, got
        return
    assert got["kinds"] == case["kinds"]
    assert got["refs"] == case["refs"]
    assert got["stale_kinds"] == case["stale_kinds"]
    assert got["note"] == case["note"]


def test_resolve_refs_maps_rest_states_and_dedupes():
    issues = {
        "o/a#1": {"state": "open"},
        "o/a#2": {"state": "closed"},
        "o/a#3": {"state": "closed", "pull_request": {"merged_at": "2026-03-27T00:00:00Z"}},
        "o/a#4": {"state": "closed", "pull_request": {"merged_at": None}},
        "o/a#5": None,
        "o/a#6": {"message": "Not Found"},
    }
    calls = []

    def fetch(ref, timeout):
        calls.append(ref)
        return issues[ref]

    got = v.resolve_refs(list(issues) + ["o/a#1"], fetch=fetch)
    assert got == {"o/a#1": "OPEN", "o/a#2": "CLOSED", "o/a#3": "MERGED", "o/a#4": "CLOSED",
                   "o/a#5": None, "o/a#6": None}
    assert sorted(calls) == sorted(issues)


def test_resolve_refs_failure_degrades_to_none():
    def boom(ref, timeout):
        raise RuntimeError("network")

    assert v.resolve_refs(["o/a#1"], fetch=boom) == {"o/a#1": None}


def test_resolve_refs_slow_lookup_is_none_not_a_hang():
    import time

    def slow(ref, timeout):
        time.sleep(3)
        return {"state": "open"}

    t0 = time.time()
    assert v.resolve_refs(["o/a#1"], fetch=slow, timeout=0.2) == {"o/a#1": None}
    assert time.time() - t0 < 2


def test_ref_note_names_only_changed_refs():
    states = {"o/a#1": "OPEN", "o/a#2": "CLOSED", "o/a#3": None, "o/a#4": "MERGED"}
    assert v.ref_note(states, ["o/a#1", "o/a#2", "o/a#3", "o/a#4"]) == "now: o/a#2 CLOSED, o/a#4 MERGED"
    assert v.ref_note({"o/a#1": "OPEN"}, ["o/a#1"]) is None


def test_mark_verified_replaces_older_stamp():
    from unittest.mock import patch

    from scripts import memory

    calls = []

    def fake_exec(sql, params=None):
        calls.append((sql, params))
        if sql.startswith("SELECT"):
            return [{"tags": json.dumps(["network", "verified-2026-01-01"])}]
        return []

    with patch.object(memory, "_exec", fake_exec), patch.object(memory, "_resolve_memory_id", lambda i: i):
        assert memory.mark_verified(["abc"], "2026-10-09") == 1
    update = next(c for c in calls if c[0].startswith("UPDATE"))
    assert json.loads(update[1][0]) == ["network", "verified-2026-10-09"]


def test_mark_verified_rejects_bad_date():
    from scripts import memory

    with pytest.raises(ValueError):
        memory.mark_verified(["abc"], "10/09/2026")
