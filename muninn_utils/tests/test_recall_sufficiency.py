"""Tests for muninn_utils.recall_sufficiency.

The pure layer (Verdict, term_coverage_judge, _content_terms, llm_judge_factory)
has no dependencies and always runs. The flow integration needs the flowing
mount (/mnt/skills/user/flowing) and is skipped without it; it uses a fake
recall injected via _import_recall, so it needs no Turso credentials.
"""
import os
import pytest

from muninn_utils import recall_sufficiency as rs


# ── Pure layer ───────────────────────────────────────────────────────────────

def test_content_terms_drops_stopwords_and_dupes():
    terms = rs._content_terms("What are the specs of the server for Project X?")
    assert "specs" in terms and "server" in terms and "project" in terms
    assert "the" not in terms and "are" not in terms and "what" not in terms
    assert len(terms) == len(set(terms))


def test_judge_sufficient_when_terms_covered():
    pool = [{"id": "a", "text": "server specs for project foo", "tags": ["infra"]}]
    v = rs.term_coverage_judge("server specs project", pool, threshold=0.66)
    assert v.sufficient is True


def test_judge_insufficient_names_gap_and_reformulation():
    pool = [{"id": "a", "text": "server specs", "tags": []}]
    v = rs.term_coverage_judge("server specs allergies rashes", pool, threshold=1.0)
    assert v.sufficient is False
    assert "allergies" in v.gap and "rashes" in v.gap
    # reformulation searches exactly the missing terms
    assert "allergies" in v.reformulation and "rashes" in v.reformulation


def test_judge_empty_question_is_trivially_sufficient():
    assert rs.term_coverage_judge("", []).sufficient is True


def test_llm_judge_factory_parses_fenced_json():
    def fake_model(_prompt):
        return '```json\n{"sufficient": false, "gap": "missing X", ' \
               '"reformulation": "search X"}\n```'
    judge = rs.llm_judge_factory(fake_model)
    v = judge("q", [])
    assert v.sufficient is False
    assert v.gap == "missing X" and v.reformulation == "search X"


# ── Flow integration (needs flowing mount; fake recall, no creds) ────────────

_HAS_FLOWING = os.path.exists("/mnt/skills/user/flowing/scripts/flowing.py")
mount = pytest.mark.skipif(not _HAS_FLOWING, reason="flowing mount absent")


def _fake_recall_factory(by_query):
    """by_query: dict query-substring -> list[dict]. Default empty otherwise."""
    def fake(query, n=6):
        for key, hits in by_query.items():
            if key in query:
                return hits[:n]
        return []
    return fake


@mount
def test_loop_satisfied_first_pass(monkeypatch):
    hits = [{"id": "1", "summary": "server specs project", "tags": ["infra"]}]
    monkeypatch.setattr(rs, "_import_recall",
                        lambda: _fake_recall_factory({"server": hits}))
    state = rs.recall_until_sufficient("server specs project", max_iters=4, n=5)
    assert state.satisfied is True
    assert state.stalled is False
    assert state.iters == 1
    assert len(state.pool) == 1


@mount
def test_loop_stalls_on_no_progress(monkeypatch):
    # 'flibbertigibbet' is never returned -> gap repeats, pool stops growing.
    hits = [{"id": "1", "summary": "server specs", "tags": []}]
    monkeypatch.setattr(rs, "_import_recall",
                        lambda: _fake_recall_factory({"server": hits,
                                                       "specs": hits}))
    state = rs.recall_until_sufficient(
        "server specs flibbertigibbet", max_iters=4, n=5,
        judge=lambda q, p: rs.term_coverage_judge(q, p, threshold=1.0),
    )
    assert state.satisfied is False
    assert state.stalled is True
    # stop at the no-progress detection, not the full budget
    assert state.iters <= 3


@mount
def test_loop_dedupes_accumulated_pool(monkeypatch):
    hits = [{"id": "1", "summary": "alpha", "tags": []},
            {"id": "1", "summary": "alpha", "tags": []},   # dup id
            {"id": "2", "summary": "beta", "tags": []}]
    monkeypatch.setattr(rs, "_import_recall",
                        lambda: _fake_recall_factory({"alpha": hits}))
    state = rs.recall_until_sufficient("alpha", max_iters=2, n=5)
    ids = [m["id"] for m in state.pool]
    assert ids.count("1") == 1   # deduped
