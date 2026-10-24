"""Tests for muninn_utils.satisfaction_skew (issue #85).

All tests inject a synthetic ``memories`` list — no Turso, no live creds.
They pin the measurement semantics the issue's definition-of-done depends on:
the headline ratio, the monthly trend, shape normalisation across tag-spelling
drift, and the unshaped ("possible emerging shape") counter.
"""
from __future__ import annotations

import json

from muninn_utils.satisfaction_skew import (
    measure_skew,
    format_report,
    _tagset,
    _month,
    _ratio,
    SHAPE_TAGS,
)


def _mem(tags, created_at, mid="x"):
    return {"id": mid, "tags": tags, "created_at": created_at, "summary": "s"}


# ── helpers ──────────────────────────────────────────────────────────────────

def test_tagset_handles_json_list_and_comma_and_none():
    assert _tagset({"tags": '["a", "b"]'}) == {"a", "b"}
    assert _tagset({"tags": ["a", "b"]}) == {"a", "b"}
    assert _tagset({"tags": "a, b ,c"}) == {"a", "b", "c"}
    assert _tagset({"tags": None}) == set()
    assert _tagset({"tags": "[bad json"}) == set()
    assert _tagset({}) == set()


def test_month_prefers_created_at_then_valid_from():
    assert _month({"created_at": "2026-06-14T10:00:00"}) == "2026-06"
    assert _month({"valid_from": "2026-05-01"}) == "2026-05"
    assert _month({}) == ""


def test_ratio_undefined_when_no_successes():
    assert _ratio(10, 0) is None
    assert _ratio(10, 4) == 2.5


# ── headline counts + ratio ──────────────────────────────────────────────────

def test_counts_and_headline_ratio():
    rows = [
        _mem(["correction"], "2026-01-01"),
        _mem(["correction"], "2026-01-02"),
        _mem(["correction", "oskar"], "2026-02-01"),
        _mem(["satisfaction-analog", "complete-thing-in-one-pass"], "2026-06-01"),
        _mem(["satisfaction"], "2026-03-01"),   # looser tag, union only
        _mem(["world"], "2026-01-03"),          # neither
    ]
    r = measure_skew(rows)
    assert r.total == 6
    assert r.fail_count == 3
    assert r.analog_count == 1
    assert r.success_count == 2            # analog + looser 'satisfaction'
    assert r.ratio_analog == 3.0           # 3 corrections : 1 analog
    assert r.ratio_success == 1.5          # 3 : 2


def test_ratio_analog_none_when_no_analogs():
    rows = [_mem(["correction"], "2026-01-01"), _mem(["correction"], "2026-01-02")]
    r = measure_skew(rows)
    assert r.analog_count == 0
    assert r.ratio_analog is None


# ── monthly trend ────────────────────────────────────────────────────────────

def test_monthly_trend_buckets_and_sorts():
    rows = [
        _mem(["correction"], "2026-05-01"),
        _mem(["correction"], "2026-05-09"),
        _mem(["correction"], "2026-06-01"),
        _mem(["satisfaction-analog"], "2026-06-15"),
    ]
    r = measure_skew(rows)
    months = {m.month: m for m in r.monthly}
    assert list(months) == sorted(months)          # sorted ascending
    assert months["2026-05"].fail == 2
    assert months["2026-05"].analog == 0
    assert months["2026-05"].ratio is None          # no analog that month
    assert months["2026-06"].fail == 1
    assert months["2026-06"].analog == 1
    assert months["2026-06"].ratio == 1.0


# ── shape normalisation (the register's SHAPE EVOLUTION input) ───────────────

def test_shape_spelling_variants_normalise_to_one_shape():
    rows = [
        _mem(["satisfaction-analog", "first-principles-system-figure-out"], "2026-06-01"),
        _mem(["satisfaction-analog", "first-principles-figureout"], "2026-06-02"),
        _mem(["satisfaction-analog", "first-principles"], "2026-06-03"),
    ]
    r = measure_skew(rows)
    assert r.shape_distribution["first-principles-system-figure-out"] == 3
    assert r.unshaped_analogs == 0


def test_unshaped_analog_flagged_as_emerging():
    rows = [
        _mem(["satisfaction-analog", "complete-thing-in-one-pass"], "2026-06-01"),
        _mem(["satisfaction-analog", "functional-emotions"], "2026-05-26"),  # no shape
    ]
    r = measure_skew(rows)
    assert r.shape_distribution["complete-thing-in-one-pass"] == 1
    assert r.unshaped_analogs == 1


def test_empirical_verification_is_a_tracked_shape():
    # issue #85: the 4th shape must be countable so the 2-3-instance promotion
    # bar is checkable.
    assert "empirical-verification" in SHAPE_TAGS
    rows = [
        _mem(["satisfaction-analog", "codec-eval"], "2026-07-01"),
        _mem(["satisfaction-analog", "paper-verification"], "2026-06-04"),
        _mem(["satisfaction-analog", "parity"], "2026-06-25"),
    ]
    r = measure_skew(rows)
    assert r.shape_distribution["empirical-verification"] == 3


# ── serialisation + formatting ───────────────────────────────────────────────

def test_to_dict_is_json_serialisable():
    r = measure_skew([_mem(["correction"], "2026-01-01")])
    d = r.to_dict()
    json.dumps(d)                                   # must not raise
    assert isinstance(d["monthly"], list)
    assert d["fail_count"] == 1


def test_format_report_renders_key_lines():
    r = measure_skew([
        _mem(["correction"], "2026-01-01"),
        _mem(["satisfaction-analog", "cross-frame-bridge"], "2026-06-01"),
    ])
    out = format_report(r)
    assert "SATISFACTION-SKEW REPORT" in out
    assert "MONTHLY TREND" in out
    assert "SHAPE DISTRIBUTION" in out
    assert "cross-frame-bridge" in out


def test_empty_corpus_is_safe():
    r = measure_skew([])
    assert r.total == 0
    assert r.ratio_analog is None
    assert r.monthly == []
    format_report(r)                                # must not raise
