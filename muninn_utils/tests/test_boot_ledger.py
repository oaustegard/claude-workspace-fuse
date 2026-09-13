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

from muninn_utils import boot_ledger as bl

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


# ── fire attribution (#84 follow-up: the counter was blind by construction) ──

def test_dispatch_targets_parses_trigger_text_and_skips_self():
    txt = ("GITHUB WORK — DESIRE TRIGGER\n"
           "→ FIRST tool call: config_get('github-procedures'). NOT optional.\n"
           "see also config_get(\"spoke-registry\") and config_get('github-routing')")
    assert bl.dispatch_targets(txt, key="github-routing") == {
        "github-procedures", "spoke-registry"}


def test_dispatch_targets_empty_when_no_dispatch():
    assert bl.dispatch_targets("Voice: Corvid. Lead with the answer.", "voice") == set()
    assert bl.dispatch_targets("", "x") == set()


def _entry(key, value="", fires=0, category="ops", chars=None):
    return bl.Entry(key=key, category=category,
                    chars=chars if chars is not None else len(value),
                    value=value, logged_fires=fires)


def test_payload_fires_attribute_back_to_the_dispatching_trigger():
    """A working trigger is never config_get'd — its payload is. The trigger's
    own count stays 0; attribution is what makes it visible."""
    trigger = _entry("github-routing",
                     "when a repo URL appears → config_get('github-procedures')" + "x" * 500)
    rows = bl.build_ledger([trigger], [], fire_counts={"github-procedures": 9})
    row = rows[0]
    assert row.logged_fires == 0          # unchanged: nobody re-reads the trigger
    assert row.attributed_fires == 9      # the payload read is the evidence
    assert row.dispatch == ("github-procedures",)


def test_attribution_sums_own_and_dispatched_fires():
    e = _entry("public-prose-trigger",
               "config_get('muninn-voice-signature') then config_get('blog-post-platform')",
               fires=2)
    rows = bl.build_ledger([e], [], fire_counts={
        "muninn-voice-signature": 5, "blog-post-platform": 3})
    assert rows[0].attributed_fires == 10


def test_build_ledger_without_fire_counts_is_backward_compatible():
    e = _entry("thesis-discipline", "config_get('thesis-discipline-check')", fires=4)
    rows = bl.build_ledger([e], [])
    assert rows[0].attributed_fires == rows[0].logged_fires == 4


def test_demotion_spares_a_trigger_whose_payload_fired():
    big = "config_get('backend-impl-protocol')" + "y" * 600
    e = _entry("backend-impl-trigger", big)
    fired = bl.build_ledger([e], [], fire_counts={"backend-impl-protocol": 1})
    assert bl.demotion_candidates(fired) == []
    silent = bl.build_ledger([e], [], fire_counts={})
    assert [r.key for r in bl.demotion_candidates(silent)] == ["backend-impl-trigger"]


def test_load_fire_counts_tolerates_pre_migration_db():
    def fake_exec(sql, args=None):
        if "PRAGMA" in sql:
            return [{"name": "key"}, {"name": "value"}, {"name": "boot_load"}]
        raise AssertionError("must not query fire_count without the column")
    assert bl.load_fire_counts(fake_exec) == {}


def test_load_fire_counts_reads_every_key_not_just_boot_loaded():
    def fake_exec(sql, args=None):
        if "PRAGMA" in sql:
            return [{"name": "key"}, {"name": "fire_count"}]
        assert "boot_load" not in sql, "reference keys must not be filtered out"
        return [{"key": "github-procedures", "fire_count": 7},
                {"key": "bike-coach-protocol", "fire_count": 4}]
    assert bl.load_fire_counts(fake_exec) == {
        "github-procedures": 7, "bike-coach-protocol": 4}


# ── measurement-window state (PR: cut-on-attr guard) ─────────────────────────

def _row(key, *, attributed=0, kind="ops", chars=500, hits=0):
    from muninn_utils.boot_ledger import LedgerRow
    return LedgerRow(key=key, category="ops", kind=kind, chars=chars,
                     tokens=chars // 4, hits=hits, months=0, recent_hits=0,
                     chars_per_hit=float(chars), logged_fires=0,
                     attributed_fires=attributed, last_fired=None,
                     dispatch=[], curated_terms=False)


def test_window_state_not_recording_when_no_attributed_fires():
    from muninn_utils.boot_ledger import window_state
    s = window_state([_row("a"), _row("b")], None, today="2026-10-01")
    assert s["verdict"] == "NOT RECORDING"
    assert "MUNINN_INSTRUMENT_FIRES" in s["why"]


def test_window_state_delivery_gap_when_fires_are_stale():
    from muninn_utils.boot_ledger import window_state
    s = window_state([_row("a", attributed=9)], "2026-09-01T00:00:00Z", today="2026-10-01")
    assert s["verdict"] == "DELIVERY GAP"


def test_window_state_immature_before_min_days():
    from muninn_utils.boot_ledger import window_state
    s = window_state([_row("a", attributed=9)], "2026-08-26T00:00:00Z", today="2026-08-27")
    assert s["verdict"] == "IMMATURE"
    assert "2026-08-24" in s["why"]


def test_window_state_usable_after_a_full_window():
    from muninn_utils.boot_ledger import window_state
    s = window_state([_row("a", attributed=30)], "2026-09-20T00:00:00Z", today="2026-09-21")
    assert s["verdict"] == "USABLE"


def test_summarize_suppresses_demotion_list_unless_usable():
    from muninn_utils.boot_ledger import summarize, window_state
    rows = [_row("fat-unused-entry", chars=900)]
    s = window_state(rows, None, today="2026-08-27")
    out = summarize(rows, 8, 3000, s)
    assert "SUPPRESSED" in out
    assert "`fat-unused-entry`" not in out
    assert "Cut on `attr`, never on `logged`" in out


def test_summarize_renders_candidates_when_usable():
    from muninn_utils.boot_ledger import summarize, window_state
    rows = [_row("fat-unused-entry", chars=900), _row("used", attributed=30)]
    s = window_state(rows, "2026-09-20T00:00:00Z", today="2026-09-21")
    out = summarize(rows, 8, 3000, s)
    assert "SUPPRESSED" not in out
    assert "`fat-unused-entry`" in out


def test_render_table_omits_the_logged_column():
    from muninn_utils.boot_ledger import render_table
    out = render_table([_row("a", attributed=3)])
    assert "logged" not in out
    assert "attr" in out
