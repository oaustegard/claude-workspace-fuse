"""Tests for muninn_utils.boot_ledger (issue #84).

Definition of done, encoded as tests:
  * cost is exact (chars straight through; token estimate present),
  * the fire proxy counts domain references and buckets them by month,
  * ranking puts worst cost/fire first,
  * demotion_candidates only ever proposes trigger/ops zero-fire entries,
  * identity entries are never demotion candidates,
  * the go-forward instrument (config_fire) increments boot-loaded keys only.

Pure fixtures — no live Turso. The Turso adapters take an injectable exec_fn,
exercised here with an in-memory fake.
"""
from __future__ import annotations

import pytest

from muninn_utils.boot_ledger import (
    Entry,
    Memory,
    LedgerRow,
    estimate_tokens,
    extract_terms,
    match_terms_for,
    kind_for,
    memory_matches,
    build_ledger,
    demotion_candidates,
    render_table,
    load_boot_entries,
    load_memory_corpus,
)


# ── cost ────────────────────────────────────────────────────────────────────

def test_estimate_tokens_nonzero_and_scales():
    assert estimate_tokens("") == 0
    small = estimate_tokens("hello world")
    big = estimate_tokens("hello world " * 100)
    assert 0 < small < big


# ── term extraction / matching ──────────────────────────────────────────────

def test_extract_terms_hyphen_aware():
    terms = extract_terms("writing a tree-sitter grammar")
    assert "tree-sitter" in terms
    assert "tree" in terms and "sitter" in terms
    assert "a" not in terms


def test_match_terms_curated_vs_auto():
    curated_terms, curated = match_terms_for("github-routing")
    assert curated is True
    assert "github" in curated_terms
    auto_terms, curated2 = match_terms_for("some-unknown-trigger")
    assert curated2 is False
    # generic suffix "trigger" dropped, domain token kept
    assert "some" in auto_terms and "unknown" in auto_terms
    assert "trigger" not in auto_terms


def test_memory_matches_whole_term_not_substring():
    assert memory_matches({"github", "commit"}, {"github"})
    # "pr" must not match inside "print"
    assert not memory_matches({"print"}, {"pr"})


def test_memory_matches_multipart_phrase_requires_all_parts():
    assert memory_matches({"cold", "start", "turso"}, {"cold-start"})
    assert not memory_matches({"cold"}, {"cold-start"})


def test_kind_classification():
    assert kind_for("github-routing", "ops") == "trigger"
    assert kind_for("muninn-voice-signature", "profile") == "catalog"
    assert kind_for("identity", "profile") == "identity"
    assert kind_for("proxy-503-retry-pattern", "ops") == "ops"


# ── ledger build / ranking ──────────────────────────────────────────────────

def _corpus():
    # github referenced in 3 memories across 2 months; blog in 1; nothing for
    # the dead trigger.
    return [
        Memory("2026-05", extract_terms("opened a github pull request and pushed a commit")),
        Memory("2026-06", extract_terms("github issue triage, new branch")),
        Memory("2026-06", extract_terms("github actions failing on the pr")),
        Memory("2026-06", extract_terms("wrote a blog post, prose about writing")),
    ]


def _entries():
    return [
        Entry("github-routing", "ops", chars=1900),
        Entry("blog-writing-trigger", "ops", chars=3300),
        Entry("dead-widget-trigger", "ops", chars=800),   # no corpus references
        Entry("identity", "profile", chars=250),
    ]


def test_build_ledger_counts_hits_and_months():
    rows = {r.key: r for r in build_ledger(_entries(), _corpus())}
    assert rows["github-routing"].hits == 3
    assert rows["github-routing"].months == 2
    assert rows["blog-writing-trigger"].hits == 1
    assert rows["dead-widget-trigger"].hits == 0


def test_build_ledger_ranks_worst_cost_per_fire_first():
    rows = build_ledger(_entries(), _corpus())
    # zero-fire entry (chars_per_hit == chars == 800) should outrank the
    # frequently-referenced github entry.
    assert rows[0].key == "dead-widget-trigger"
    # monotonic non-increasing by chars_per_hit
    cph = [r.chars_per_hit for r in rows]
    assert cph == sorted(cph, reverse=True)


def test_demotion_candidates_only_zerofire_trigger_ops():
    rows = build_ledger(_entries(), _corpus())
    cands = demotion_candidates(rows)
    keys = {r.key for r in cands}
    assert keys == {"dead-widget-trigger"}          # only the zero-fire ops entry
    # identity never demoted even at zero fire
    id_entry = Entry("intellectual_interests", "profile", chars=1600)
    rows2 = build_ledger([id_entry], [])            # empty corpus → 0 hits
    assert demotion_candidates(rows2) == []


def test_demotion_candidates_respects_min_chars():
    rows = build_ledger([Entry("tiny-trigger", "ops", chars=100)], [])
    assert demotion_candidates(rows, min_chars=400) == []
    assert demotion_candidates(rows, min_chars=50)[0].key == "tiny-trigger"


def test_render_table_marks_zero_hits():
    rows = build_ledger(_entries(), _corpus())
    table = render_table(rows)
    assert "∞(0 hits)" in table
    assert "`dead-widget-trigger`" in table


# ── Turso adapters with an injected fake exec ───────────────────────────────

class FakeExec:
    """Minimal stand-in for remembering's _exec over config + memories."""
    def __init__(self, has_fire=True):
        self.has_fire = has_fire

    def __call__(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith("PRAGMA table_info(config)"):
            cols = [{"name": n} for n in ("key", "value", "category", "boot_load")]
            if self.has_fire:
                cols += [{"name": "fire_count"}, {"name": "last_fired"}]
            return cols
        if "FROM config WHERE boot_load=1" in s:
            row = {"key": "github-routing", "category": "ops", "len": 1900,
                   "value": "x" * 1900}
            if self.has_fire:
                row["fire_count"] = 5
                row["last_fired"] = "2026-07-01T00:00:00Z"
            return [row]
        if "FROM memories WHERE deleted_at IS NULL" in s:
            return [
                {"created_at": "2026-06-01T00:00:00Z", "summary": "github pr",
                 "tags": '["github"]', "t": "opened a pull request"},
            ]
        raise AssertionError(f"unexpected SQL: {s}")


def test_load_boot_entries_reads_fire_columns():
    entries = load_boot_entries(FakeExec(has_fire=True))
    assert len(entries) == 1
    e = entries[0]
    assert e.key == "github-routing" and e.chars == 1900
    assert e.logged_fires == 5 and e.last_fired == "2026-07-01T00:00:00Z"


def test_load_boot_entries_without_fire_columns():
    entries = load_boot_entries(FakeExec(has_fire=False))
    assert entries[0].logged_fires == 0 and entries[0].last_fired is None


def test_load_memory_corpus_projects_month_and_terms():
    mems = load_memory_corpus(FakeExec())
    assert len(mems) == 1
    assert mems[0].month == "2026-06"
    assert "github" in mems[0].terms


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
