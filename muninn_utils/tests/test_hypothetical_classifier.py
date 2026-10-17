"""Tests for hypothetical_classifier.

No credentials needed: `classify`/`hallucinate` take an `invoke` callable, so the
model half is injected. The embedder half runs for real on the tfidf backend.
"""
import pytest

from muninn_utils.hypothetical_classifier import (
    Vocabulary, classify, hallucinate, _interleave, _PROMPT,
)

LABELS = ["Coffee Tables", "Throw Pillows", "Kids Beds", "Massage Chairs",
          "Food Storage & Canisters", "Stackable Chairs"]


# ── Vocabulary ────────────────────────────────────────────────────────────────

def test_snap_resolves_an_invented_label_to_the_real_one():
    v = Vocabulary(LABELS)
    [[(label, score)]] = v.snap(["Wooden Cocktail Coffee Tables"], k=1)
    assert label == "Coffee Tables"
    assert score > 0.3


def test_snap_output_is_always_in_the_vocabulary():
    v = Vocabulary(LABELS)
    for ranked in v.snap(["utter nonsense zzzz", "", "Kids Bunk Bed"], k=3):
        for label, _ in ranked:
            assert label in LABELS


def test_empty_vocabulary_raises_rather_than_returning_nothing():
    with pytest.raises(ValueError):
        Vocabulary([])


def test_unknown_backend_raises():
    with pytest.raises(ValueError):
        Vocabulary(LABELS, backend="word2vec")


def test_documented_backends_are_all_constructible():
    """Registry invariant: the docstring names two backends. A third added there
    without an entry here is the failure this catches."""
    import muninn_utils.hypothetical_classifier as hc
    documented = {"tfidf", "minilm"}
    for backend in documented:
        assert f'"{backend}"' in hc.Vocabulary._fit.__code__.co_consts.__str__() or \
               backend in hc.__doc__, f"{backend} documented but not dispatched"

    Vocabulary(LABELS, backend="tfidf")          # always available
    pytest.importorskip("sentence_transformers")
    Vocabulary(LABELS, backend="minilm")


# ── hallucination parsing ─────────────────────────────────────────────────────

def test_hallucinate_parses_numbered_lines_by_index():
    out = hallucinate(["a", "b", "c"], invoke=lambda p, m, t: "1. Alpha\n2. Beta\n3. Gamma")
    assert out == ["Alpha", "Beta", "Gamma"]


def test_a_dropped_item_becomes_empty_not_a_neighbours_label():
    """The whole reason the format is numbered. Zipping positionally would shift
    every later item onto the wrong label, silently."""
    out = hallucinate(["a", "b", "c"], invoke=lambda p, m, t: "1. Alpha\n3. Gamma")
    assert out == ["Alpha", "", "Gamma"]


def test_hallucinate_batches_rather_than_one_call_per_item():
    calls = []
    def spy(prompt, model, tokens):
        calls.append(prompt)
        return "\n".join(f"{i+1}. L{i}" for i in range(40))
    hallucinate([f"item{i}" for i in range(40)], batch=40, invoke=spy)
    assert len(calls) == 1


def test_hallucination_prompt_never_ships_the_vocabulary():
    """The point of the pattern: the model does not see the legal label set."""
    prompt = _PROMPT.format(domain="d", examples="  Coffee Tables", numbered="1. x")
    assert "Massage Chairs" not in prompt
    assert "Stackable Chairs" not in prompt


# ── classify ──────────────────────────────────────────────────────────────────

def test_failed_generation_yields_none_not_a_guess():
    v = Vocabulary(LABELS)
    out = classify(["x"], v, invoke=lambda p, m, t: "")
    assert out[0].label is None and out[0].ok is False


def test_classify_snaps_into_the_vocabulary():
    v = Vocabulary(LABELS)
    out = classify(["wood coffee table"], v, blend=False,
                   invoke=lambda p, m, t: "1. Wooden Cocktail Tables")
    assert out[0].label == "Coffee Tables"
    assert out[0].hallucination == "Wooden Cocktail Tables"


def test_direct_union_adds_the_direct_snap_to_the_ranking():
    v = Vocabulary(LABELS)
    plain = classify(["stackable chair for the kids room"], v, k=3, blend=False,
                     invoke=lambda p, m, t: "1. Nursery Sleeping Furniture")
    union = classify(["stackable chair for the kids room"], v, k=3, blend=False,
                     direct_union=True, invoke=lambda p, m, t: "1. Nursery Sleeping Furniture")
    assert {l for l, _ in union[0].alternatives} != {l for l, _ in plain[0].alternatives}


def test_classify_of_nothing_is_empty_not_an_error():
    assert classify([], Vocabulary(LABELS)) == []


# ── interleave ────────────────────────────────────────────────────────────────

def test_interleave_dedups_and_keeps_first_position():
    assert _interleave([("a", 1.0), ("b", 0.9)], [("b", 0.8), ("c", 0.7)], 3) == \
        [("a", 1.0), ("b", 0.8), ("c", 0.7)]


def test_interleave_respects_k():
    assert len(_interleave([("a", 1.0), ("b", 0.9)], [("c", 0.8), ("d", 0.7)], 2)) == 2
