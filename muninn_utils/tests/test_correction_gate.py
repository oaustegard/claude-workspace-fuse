"""Tests for muninn_utils.correction_gate (issue #83).

Definition of done, encoded as tests:
  * adding a trigger runs the gate,
  * a deliberately-regressing trigger is rejected,
  * a genuine fix passes.

Plus the held-in semantics (a correction that fixes nothing is rejected),
the recall-slice adapter with a stubbed runner (no Turso), the budget guard,
and the therapy write-path entry point.
"""
from __future__ import annotations

import pytest

from muninn_utils.correction_gate import (
    Case,
    GateResult,
    extract_terms,
    fired_triggers,
    gate_trigger_correction,
    gate_recall_correction,
    gate_config_correction,
    check_budget,
    load_benchmark,
    _parse_trigger_list,
)


# A plausible baseline trigger set (stands in for the live recall-triggers).
BASE = ["fuse", "memfs", "boot-recovery", "turso", "whtwnd", "reindex"]

# Held-out inputs seeded from real behaviour (mirrors the seed benchmark).
HELD_OUT = [
    Case("fuse-q", "how does the /mnt/muninn fuse mount project memories?", frozenset()),
    Case("boot-q", "cold start boot degraded, codeload 403, need add_repo", frozenset()),
    Case("turso-q", "first recall failed with a 503 from the proxy", frozenset()),
    Case("calendar", "what meetings are on my calendar tomorrow?", frozenset()),
]

# The real diagnosed miss (session 854f6b7c): tree-sitter memories weren't
# surfaced because no trigger fired.
MOTIVATING = Case(
    name="tree-sitter-miss",
    input="writing a tree-sitter grammar, does the scanner.cc link?",
    expected=frozenset({"tree-sitter"}),
    source="854f6b7c",
)


# ── term extraction / firing ────────────────────────────────────────────────

def test_extract_terms_hyphen_aware():
    terms = extract_terms("writing a tree-sitter grammar")
    assert "tree-sitter" in terms      # whole hyphenated token
    assert "tree" in terms and "sitter" in terms  # split parts
    assert "a" not in terms            # too short / stop word


def test_fired_triggers_intersection():
    fired = fired_triggers("the fuse mount question", ["fuse", "memfs"])
    assert fired == {"fuse"}


def test_fired_triggers_empty_when_no_overlap():
    assert fired_triggers("plain calendar lookup", BASE) == set()


# ── DoD: genuine fix passes ─────────────────────────────────────────────────

def test_genuine_fix_passes():
    gate = gate_trigger_correction(
        before_triggers=BASE,
        after_triggers=BASE + ["tree-sitter"],
        held_in=MOTIVATING,
        held_out=HELD_OUT,
    )
    assert gate.passed is True
    assert gate.held_in_passed is True
    assert gate.regressions == []
    assert bool(gate) is True  # __bool__ reads as "passed"


# ── DoD: deliberately-regressing trigger is rejected ────────────────────────

def test_regressing_trigger_rejected():
    # "files" fires on the fuse held-out input ("...project memories?" -> no,
    # but add an input with 'files'); use 'mount' which fires on fuse-q.
    gate = gate_trigger_correction(
        before_triggers=BASE,
        after_triggers=BASE + ["mount"],  # fires on the fuse held-out input
        held_in=Case("bloat", "the fuse mount", frozenset({"mount"})),
        held_out=HELD_OUT,
    )
    assert gate.passed is False
    assert any(r["case"] == "fuse-q" for r in gate.regressions)
    assert "mount" in gate.regressions[0]["added"]


def test_regressing_trigger_firing_on_calendar_rejected():
    gate = gate_trigger_correction(
        before_triggers=BASE,
        after_triggers=BASE + ["calendar"],  # false-positive on the negative case
        held_in=Case("cal", "check my calendar", frozenset({"calendar"})),
        held_out=HELD_OUT,
    )
    assert gate.passed is False
    assert any(r["case"] == "calendar" for r in gate.regressions)


# ── held-in semantics ───────────────────────────────────────────────────────

def test_correction_that_fixes_nothing_rejected():
    # The motivating case already passes under the baseline -> not a correction.
    already = Case("noop", "the fuse mount", expected=frozenset({"fuse"}))
    gate = gate_trigger_correction(
        before_triggers=BASE,           # already contains 'fuse'
        after_triggers=BASE + ["extra"],
        held_in=already,
        held_out=HELD_OUT,
    )
    assert gate.passed is False
    assert gate.held_in_passed is False
    assert "fixes nothing" in gate.held_in_reason


def test_correction_that_does_not_fix_its_own_case_rejected():
    gate = gate_trigger_correction(
        before_triggers=BASE,
        after_triggers=BASE + ["something-else"],  # doesn't fire on motivating input
        held_in=MOTIVATING,
        held_out=HELD_OUT,
    )
    assert gate.passed is False
    assert gate.held_in_passed is False
    assert "does not catch" in gate.held_in_reason


def test_intended_held_out_change_is_allowed():
    # A held-out case flagged intended may change without counting as regression.
    ho = [Case("fuse-q", "the fuse mount question", frozenset(), intended=True)]
    gate = gate_trigger_correction(
        before_triggers=BASE,
        after_triggers=BASE + ["mount"],  # would fire on the intended case
        held_in=Case("mount-fix", "the fuse mount", frozenset({"mount"})),
        held_out=ho,
    )
    assert gate.passed is True
    assert gate.regressions == []


# ── recall slice (stubbed runner, no Turso) ─────────────────────────────────

def test_recall_slice_differential():
    # Simulate a correction (e.g. retagging) that changes recall for the
    # motivating query but leaves an unrelated past query untouched.
    corpus_before = {"tree-sitter setup?": {"m1"}, "fuse mount?": {"m9"}}
    corpus_after = {"tree-sitter setup?": {"m1", "m2"}, "fuse mount?": {"m9"}}

    def before_recall(q):
        return corpus_before.get(q, set())

    def after_recall(q):
        return corpus_after.get(q, set())

    gate = gate_recall_correction(
        before_recall=before_recall,
        after_recall=after_recall,
        held_in=Case("recall-miss", "tree-sitter setup?", frozenset({"m2"}), kind="recall"),
        held_out=[Case("fuse-recall", "fuse mount?", frozenset(), kind="recall")],
    )
    assert gate.passed is True


def test_recall_slice_detects_unrelated_regression():
    corpus_before = {"tree-sitter setup?": {"m1"}, "fuse mount?": {"m9"}}
    # The correction accidentally changes the unrelated fuse query too.
    corpus_after = {"tree-sitter setup?": {"m1", "m2"}, "fuse mount?": {"m9", "m8"}}

    gate = gate_recall_correction(
        before_recall=lambda q: corpus_before.get(q, set()),
        after_recall=lambda q: corpus_after.get(q, set()),
        held_in=Case("recall-miss", "tree-sitter setup?", frozenset({"m2"}), kind="recall"),
        held_out=[Case("fuse-recall", "fuse mount?", frozenset(), kind="recall")],
    )
    assert gate.passed is False
    assert gate.regressions[0]["added"] == ["m8"]


# ── budget guard ────────────────────────────────────────────────────────────

def test_budget_within_limit():
    assert check_budget(1000, 1200, max_chars=2000) is None


def test_budget_over_total():
    reason = check_budget(1000, 2500, max_chars=2000)
    assert reason and "budget" in reason


def test_budget_over_growth_cap():
    reason = check_budget(1000, 1600, max_chars=10000, max_growth=500)
    assert reason and "grow" in reason


# ── therapy write-path entry point ──────────────────────────────────────────

def _bench():
    return {"trigger": HELD_OUT, "recall": [], "reindex": []}


def test_gate_config_correction_trigger_pass():
    import json
    gate = gate_config_correction(
        "recall-triggers", "ops",
        json.dumps(BASE),
        json.dumps(BASE + ["tree-sitter"]),
        motivating=MOTIVATING,
        benchmark=_bench(),
    )
    assert isinstance(gate, GateResult)
    assert gate.passed is True


def test_gate_config_correction_trigger_reject():
    import json
    gate = gate_config_correction(
        "recall-triggers", "ops",
        json.dumps(BASE),
        json.dumps(BASE + ["mount"]),
        motivating=Case("m", "the fuse mount", frozenset({"mount"})),
        benchmark=_bench(),
    )
    assert gate.passed is False


def test_gate_config_correction_skips_when_nothing_measurable():
    # A non-trigger ops entry within budget -> None (caller proceeds).
    gate = gate_config_correction(
        "communication-patterns", "ops",
        "old value", "new value within budget",
        benchmark=_bench(),
    )
    assert gate is None


def test_gate_config_correction_ops_over_budget_rejected():
    gate = gate_config_correction(
        "some-ops", "ops",
        "x", "y" * 10,
        benchmark=_bench(),
        max_boot_chars=5,
    )
    assert gate is not None and gate.passed is False


# ── benchmark loading ───────────────────────────────────────────────────────

def test_load_seed_benchmark_ships_real_cases():
    bench = load_benchmark()
    assert len(bench["trigger"]) >= 3
    assert all(isinstance(c, Case) for c in bench["trigger"])
    assert all(c.source for c in bench["trigger"])  # every case cites a source


def test_load_missing_benchmark_is_empty():
    bench = load_benchmark("/nonexistent/path/benchmark.json")
    assert bench == {"trigger": [], "recall": [], "reindex": []}


def test_parse_trigger_list_json_and_plain():
    assert _parse_trigger_list('["a", "b"]') == ["a", "b"]
    assert _parse_trigger_list("a, b c") == ["a", "b", "c"]
    assert _parse_trigger_list(None) == []
    assert _parse_trigger_list("") == []
