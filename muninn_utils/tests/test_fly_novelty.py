"""Tests for fly_novelty: attractor buckets, cooldown gate, attractor cap, fields.

Fixture: the 100 newest flight-log titles as of 2026-10-16 (#140-#378), each
hand-labelled with its recurring subtopic or "-" for off-menu. created_at is
synthesized one day apart, newest first, so the date arithmetic is exact.
"""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from muninn_utils import fly_novelty as fn

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
FIXTURE = Path(__file__).parent / "fixtures" / "flight_titles_2026-10-16.json"


@pytest.fixture
def logs():
    rows = json.loads(FIXTURE.read_text())
    out = []
    for i, r in enumerate(rows):
        when = (NOW - timedelta(days=i, hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        out.append({"number": r["number"], "title": r["title"], "label": r["label"],
                    "created_at": when, "url": f"https://example/{r['number']}"})
    return out


def test_buckets_match_hand_labels(logs):
    for log in logs:
        got = fn.attractor_buckets(log["title"])
        if log["label"] == "-":
            assert got == [], (log["number"], log["title"], got)
        else:
            assert log["label"] in got, (log["number"], log["title"], got)


def test_repeat_of_recent_attractor_is_blocked(logs):
    a = fn.assess_candidate("The Lexicon Question",
                            "ATProto's new standards body and lexicon governance.", logs, now=NOW)
    assert not a["ok"]
    assert "atproto" in a["buckets"]
    assert any("'atproto'" in r for r in a["reasons"])


def test_coy_title_cannot_hide_repeat(logs):
    a = fn.assess_candidate("The Long Slide",
                            "V-Dem's latest dataset release on autocratization.", logs, now=NOW)
    assert not a["ok"] and "democracy" in a["buckets"]


def test_off_menu_candidate_passes(logs):
    a = fn.assess_candidate("Clinker and Rivets",
                            "How Viking-age shipwrights set iron rivets, from a 2026 "
                            "Journal of Maritime Archaeology excavation report.", logs, now=NOW)
    assert a["ok"], a["reasons"]
    assert a["buckets"] == []
    assert len(a["nearest"]) == 5


def test_cooldown_expires(logs):
    # 'vcs' last flown at fixture index 13 (#365); 40 days later it is open,
    # but the cap still applies because the newest 7 are dense with attractors.
    later = NOW + timedelta(days=40)
    a = fn.assess_candidate("Jujutsu revisited", "jj op log", logs, now=later)
    assert not any("'vcs'" in r for r in a["reasons"])
    assert any("cap" in r for r in a["reasons"])


def test_cap_only_applies_to_attractor_candidates(logs):
    quiet = [dict(log, title=f"Off-menu topic {i}") for i, log in enumerate(logs)]
    a = fn.assess_candidate("Jujutsu revisited", "jj op log", quiet, now=NOW)
    assert a["ok"]


def test_needs_enough_history(logs):
    with pytest.raises(ValueError):
        fn.assess_candidate("x", "y", logs[:7], now=NOW)


def test_suggest_fields_excludes_seen_and_attractors(logs):
    picks = fn.suggest_fields(logs, k=6, rng=random.Random(0))
    assert len(picks) == 6 and len(set(picks)) == 6
    seen = " ".join(log["title"].lower() for log in logs)
    for f in picks:
        assert f.lower() not in seen
        assert fn.attractor_buckets(f) == []


def test_format_assessment_shape(logs):
    a = fn.assess_candidate("ATProto again", "bluesky", logs, now=NOW)
    out = fn.format_assessment(a)
    assert out.startswith("NOVELTY GATE: BLOCKED")
    assert "nearest prior titles" in out


# ── Oskar seed topics ────────────────────────────────────────────────────────

def test_seed_matches_examples():
    assert "courts-and-executive-power" in fn.seed_matches(
        "Judge Reyes's opinion barring the administration from rescinding TPS")
    assert "web-craft" in fn.seed_matches("A whole office suite stored in the URL fragment")
    assert "art-history" in fn.seed_matches("Samson and Delilah, a painting by Lucas Cranach")
    assert fn.seed_matches("Clinker and rivets in Viking-age ships") == []


def test_seed_cooldown_blocks_recent_seed(logs):
    recent = [dict(logs[0], title="Bach's chorale harmonization as a search problem")] + logs[1:]
    a = fn.assess_candidate("Strudel and the live-coding scene",
                            "Live-coded music in the browser.", recent, now=NOW)
    assert "music-and-sound" in a["seeds"]
    assert any("'music-and-sound'" in r for r in a["reasons"])


def test_seed_not_subject_to_attractor_cap(logs):
    # The newest 7 are dense with attractors; an unflown seed still passes.
    a = fn.assess_candidate("Interurban railways of the 1920s",
                            "Ridership records of the electric interurban railway network.",
                            logs, now=NOW)
    assert a["ok"], a["reasons"]
    assert "urbanism-and-transport" in a["seeds"] and a["buckets"] == []


def test_suggest_seeds_skips_cooled_and_returns_hints(logs):
    recent = [dict(logs[0], title="Kandinsky's painting as proto-digital art")] + logs[1:]
    picks = fn.suggest_seeds(recent, k=20, now=NOW, rng=random.Random(1))
    names = [n for n, _ in picks]
    assert "art-history" not in names
    assert all(h for _, h in picks)
    assert len(names) == len(set(names))
