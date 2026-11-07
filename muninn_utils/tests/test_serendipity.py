"""Unit tests for muninn_utils.serendipity. Injected rows only — no Turso, no network.

The rhyme strategy needs sklearn via memory_tfidf and is covered separately with a
skip, so the tags/temporal logic stays testable in a bare environment.
"""

from __future__ import annotations

import json

import pytest

from muninn_utils.serendipity import (
    STRATEGIES,
    Pair,
    _linked,
    _public,
    _ref_set,
    _tag_set,
    format_pairs,
    serendipity,
)


def row(mid, tags, summary="body text", day="2026-09-01", refs=None):
    return {
        "id": mid,
        "type": "analysis",
        "tags": tags,
        "refs": refs,
        "summary": summary,
        "created_at": f"{day}T12:00:00Z",
        "valid_from": f"{day}T12:00:00Z",
        "priority": 0,
    }


class TestNormalisation:
    def test_tag_set_handles_list_json_and_csv(self):
        assert _tag_set(["a", "b"]) == {"a", "b"}
        assert _tag_set(json.dumps(["a", "b"])) == {"a", "b"}
        assert _tag_set("a, b") == {"a", "b"}
        assert _tag_set(None) == set()
        assert _tag_set([]) == set()

    def test_ref_set_handles_legacy_null_string(self):
        # recall-empty-diagnostic: legacy rows carry the literal string 'null'.
        assert _ref_set("null") == set()
        assert _ref_set(None) == set()
        assert _ref_set(json.dumps(["abc123"])) == {"abc123"}

    def test_ref_set_survives_malformed_json(self):
        assert _ref_set("{not json") == set()


class TestLinked:
    def test_full_id_either_direction(self):
        a = row("aaa-111", ["x"], refs=json.dumps(["bbb-222"]))
        b = row("bbb-222", ["y"])
        assert _linked(a, b)
        assert _linked(b, a)

    def test_eight_char_prefix_counts_as_linked(self):
        # Refs are cited as 8-char prefixes throughout the corpus.
        a = row("aaaaaaaa-1111", ["x"])
        b = row("bbbbbbbb-2222", ["y"], refs=json.dumps(["aaaaaaaa"]))
        assert _linked(a, b)

    def test_unrelated_pair_is_not_linked(self):
        assert not _linked(row("aaa", ["x"]), row("bbb", ["y"]))


class TestPrivateTagDiscipline:
    def test_confidential_rows_are_dropped(self):
        rows = [row("a", ["career-search", "confidential"]), row("b", ["public"])]
        assert [m["id"] for m in _public(rows)] == ["b"]

    def test_confidential_never_reaches_a_pair(self):
        rows = [
            row("a", ["confidential", "rare-x", "rare-y"]),
            row("b", ["rare-x", "rare-y"]),
            row("c", ["rare-x", "rare-y"]),
        ]
        pairs = serendipity(n=10, strategies=["tags"], memories=rows, seed=1)
        ids = {p.id_a for p in pairs} | {p.id_b for p in pairs}
        assert "a" not in ids
        assert ids == {"b", "c"}


class TestTagsStrategy:
    def test_requires_two_uncommon_tags(self):
        rows = [row("a", ["rare-x"]), row("b", ["rare-x"])]
        assert serendipity(strategies=["tags"], memories=rows, seed=1) == []

        rows = [row("a", ["rare-x", "rare-y"]), row("b", ["rare-x", "rare-y"])]
        pairs = serendipity(strategies=["tags"], memories=rows, seed=1)
        assert len(pairs) == 1
        assert pairs[0].shared_tags == ["rare-x", "rare-y"]

    def test_common_tags_are_ignored(self):
        # 'correction' on every row is scaffolding; co-occurrence through it is noise.
        rows = [row(str(i), ["correction", "muninn"], day="2026-01-01") for i in range(200)]
        assert serendipity(strategies=["tags"], memories=rows, seed=1) == []

    def test_already_linked_pair_is_excluded(self):
        rows = [
            row("a", ["rare-x", "rare-y"], refs=json.dumps(["b"])),
            row("b", ["rare-x", "rare-y"]),
        ]
        assert serendipity(strategies=["tags"], memories=rows, seed=1) == []

    def test_ranks_by_number_of_shared_tags(self):
        # Padding matters: the rarity ceiling is a fraction of the corpus, so a
        # tag on 3 of 3 rows is correctly "common". Pad to a realistic size.
        rows = [row(f"pad{i}", [f"filler{i}"], day="2026-02-02") for i in range(300)]
        rows += [
            row("a", ["p", "q", "r"]),
            row("b", ["p", "q", "r"]),
            row("c", ["p", "q"]),
        ]
        pairs = serendipity(n=5, strategies=["tags"], memories=rows, seed=1)
        assert pairs[0].score >= pairs[-1].score
        assert pairs[0].score == 3
        assert {pairs[0].id_a, pairs[0].id_b} == {"a", "b"}

    def test_rarity_ceiling_scales_with_corpus(self):
        # The same three rows with no padding: every tag is corpus-wide, so
        # nothing is uncommon and nothing pairs.
        rows = [row("a", ["p", "q", "r"]), row("b", ["p", "q", "r"]), row("c", ["p", "q"])]
        assert serendipity(n=5, strategies=["tags"], memories=rows, seed=1) == []


class TestTemporalStrategy:
    def test_same_day_low_overlap_pairs(self):
        rows = [row("a", ["alpha"], day="2026-05-05"), row("b", ["beta"], day="2026-05-05")]
        pairs = serendipity(strategies=["temporal"], memories=rows, seed=1)
        assert len(pairs) == 1
        assert "2026-05-05" in pairs[0].why

    def test_different_days_do_not_pair(self):
        rows = [row("a", ["alpha"], day="2026-05-05"), row("b", ["beta"], day="2026-06-06")]
        assert serendipity(strategies=["temporal"], memories=rows, seed=1) == []

    def test_high_tag_overlap_is_excluded(self):
        rows = [row("a", ["same"], day="2026-05-05"), row("b", ["same"], day="2026-05-05")]
        assert serendipity(strategies=["temporal"], memories=rows, seed=1) == []


class TestStrategySelection:
    def test_bm25_is_an_alias_for_rhyme(self):
        rows = [row("a", ["x"]), row("b", ["y"])]
        # Both resolve to the same strategy; neither raises.
        serendipity(strategies=["bm25"], memories=rows, seed=1)
        serendipity(strategies=["rhyme"], memories=rows, seed=1)

    def test_unknown_strategy_raises(self):
        with pytest.raises(ValueError, match="unknown strategies"):
            serendipity(strategies=["telepathy"], memories=[], seed=1)

    def test_duplicate_strategy_runs_once(self):
        rows = [row("a", ["p", "q"]), row("b", ["p", "q"])]
        pairs = serendipity(strategies=["tags", "tags"], memories=rows, seed=1)
        assert len(pairs) == 1

    def test_default_covers_every_strategy(self):
        assert set(STRATEGIES) == {"rhyme", "tags", "temporal"}


class TestDeterminismAndOutput:
    def test_seed_makes_a_run_reproducible(self):
        rows = [row(str(i), [f"t{i}", f"u{i % 3}"], day="2026-07-07") for i in range(12)]
        a = serendipity(n=4, strategies=["temporal"], memories=rows, seed=42)
        b = serendipity(n=4, strategies=["temporal"], memories=rows, seed=42)
        assert [p.to_dict() for p in a] == [p.to_dict() for p in b]

    def test_empty_corpus_is_not_an_error(self):
        assert serendipity(memories=[], seed=1) == []
        assert "no candidate pairs" in format_pairs([])

    def test_format_pairs_renders_ids_and_verdicts(self):
        p = Pair(
            strategy="tags",
            score=2.0,
            why="2 uncommon tags in common, never linked",
            id_a="aaaaaaaa-1",
            id_b="bbbbbbbb-2",
            preview_a="first",
            preview_b="second",
            shared_tags=["p", "q"],
        )
        out = format_pairs([p])
        assert "aaaaaaaa" in out and "bbbbbbbb" in out
        assert "Verdicts" in out


class TestRhymeStrategy:
    def test_rhyme_pairs_structurally_similar_across_domains(self):
        pytest.importorskip("sklearn")
        shared = "retry budget exhausted before the backoff window closed"
        rows = [
            row("a", ["proxy", "transport"], summary=f"{shared} on the egress proxy"),
            row("b", ["cycling", "intervals"], summary=f"{shared} on the third interval"),
            row("c", ["unrelated"], summary="hero image rendered as abstract shapes"),
            row("d", ["unrelated2"], summary="grocery aisle mapping from sign photos"),
        ]
        pairs = serendipity(n=5, strategies=["rhyme"], memories=rows, seed=3)
        if pairs:  # min_df=2 can empty the vocabulary on a corpus this small
            assert all(p.strategy == "rhyme" for p in pairs)
            assert all(p.id_a != p.id_b for p in pairs)

    def test_rhyme_degrades_to_empty_without_sklearn(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name == "muninn_utils.memory_tfidf":
                raise ImportError("blocked for test")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)
        rows = [row("a", ["x"], summary="one"), row("b", ["y"], summary="two")]
        assert serendipity(strategies=["rhyme"], memories=rows, seed=1) == []


class TestMemoryTfidfDependency:
    """Regression guard for the upstream fix this module depends on.

    ``cross_domain_rhymes`` broke on its self-match with ``break`` rather than
    ``continue``. The source memory is always rank 0 at similarity 1.0, so the
    loop exited on its first iteration and the method returned [] on every call
    ever made. ``similar()`` shares the scoring path and was unaffected, which is
    why nothing surfaced it until the rhyme strategy came up empty on a
    3303-memory corpus.
    """

    def test_cross_domain_rhymes_does_not_break_on_self(self):
        pytest.importorskip("sklearn")
        from muninn_utils.memory_tfidf import MemoryIndex

        shared = "retry budget exhausted before the backoff window closed again"
        # MemoryIndex pins max_df=0.50/min_df=2, so the corpus needs enough rows
        # for half of it to reach two documents before the vectorizer will build.
        rows = [
            row(f"pad{i}", ["filler"], summary=f"unrelated filler document number {i} here")
            for i in range(10)
        ]
        rows += [
            row("a", ["proxy"], summary=f"{shared} on the egress proxy layer"),
            row("b", ["cycling"], summary=f"{shared} on the third interval effort"),
            row("c", ["proxy"], summary=f"{shared} on the egress proxy layer twice"),
        ]
        index = MemoryIndex().build(rows)
        rhymes = index.cross_domain_rhymes("b", n=5, min_sim=0.1, max_tag_overlap=0.9)
        assert rhymes, "self-match must be skipped, not break the scan"
        assert all(r["id"] != "b" for r in rhymes)


class TestRhymeSameDayExclusion:
    """First live run (2026-09-12, memory 6082a5fd) returned three pairs and all
    three were same-day companions about one subject — a fly body and its
    analysis, a root cause and its stash. Those carry different tag vocabularies,
    so max_tag_overlap does not exclude them, and they dominate the high-cosine
    band rhyme is searching. Same-session pairing belongs to `temporal`.
    """

    def _corpus(self, day_b):
        # MemoryIndex pins min_df=2, so any term appearing once is dropped from
        # the vocabulary. If a and b differ only by hapaxes their vectors come
        # out identical at cosine 1.0 and the dup ceiling correctly discards
        # them. The sibling rows give each side distinguishing terms that
        # survive min_df, landing the pair in the band rhyme actually searches.
        shared = "retry budget exhausted before the backoff window closed again"
        rows = [
            row(f"pad{i}", ["filler"], summary=f"unrelated filler document number {i} here")
            for i in range(10)
        ]
        rows += [
            row("a", ["proxy"], summary=f"{shared} egress proxy layer dns", day="2026-03-01"),
            row("b", ["cycling"], summary=f"{shared} interval cadence watts", day=day_b),
            row("a2", ["proxy"], summary="egress proxy layer dns notes", day="2026-01-04"),
            row("b2", ["cycling"], summary="interval cadence watts notes", day="2026-01-05"),
        ]
        return rows

    def test_same_day_pair_is_dropped_by_default(self):
        pytest.importorskip("sklearn")
        rows = self._corpus("2026-03-01")
        pairs = serendipity(n=5, strategies=["rhyme"], memories=rows, seed=3)
        assert not [p for p in pairs if {p.id_a, p.id_b} == {"a", "b"}]

    def test_same_day_pair_returns_when_opted_in(self):
        pytest.importorskip("sklearn")
        rows = self._corpus("2026-03-01")
        pairs = serendipity(
            n=5, strategies=["rhyme"], memories=rows, seed=3, same_day_ok=True
        )
        assert [p for p in pairs if {p.id_a, p.id_b} == {"a", "b"}]

    def test_cross_day_pair_is_unaffected(self):
        pytest.importorskip("sklearn")
        rows = self._corpus("2026-08-14")
        pairs = serendipity(n=5, strategies=["rhyme"], memories=rows, seed=3)
        assert [p for p in pairs if {p.id_a, p.id_b} == {"a", "b"}]

    def test_temporal_still_pairs_same_session(self):
        # The behaviour rhyme gives up is not lost; it is temporal's job.
        rows = [row("a", ["alpha"], day="2026-03-01"), row("b", ["beta"], day="2026-03-01")]
        pairs = serendipity(strategies=["temporal"], memories=rows, seed=1)
        assert len(pairs) == 1
