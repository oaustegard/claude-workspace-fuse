"""zeitgeist_delta embeds with the local Ettin model (no Gemini gateway) and applies the
2026-11-15 Ettin thresholds; the same-topic boost picks the boosted match."""
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from muninn_utils import ettin_embed
from muninn_utils import zeitgeist_delta as zd


class FakeEmbedder:
    """Gives each text the vector of the first marker word it contains, so tests set similarities."""

    def __init__(self, vectors):
        self.vectors = vectors
        self.calls = []

    def encode_long(self, texts, *, prompt="document"):
        self.calls.append(list(texts))
        out = np.array([next(v for k, v in self.vectors.items() if k in t) for t in texts],
                       dtype=np.float64)
        return out / np.linalg.norm(out, axis=1, keepdims=True)


def _unit_pair(cos):
    """Two 2-d unit vectors with the given cosine."""
    return np.array([1.0, 0.0]), np.array([cos, np.sqrt(1 - cos * cos)])


@pytest.fixture
def setup(monkeypatch):
    def _install(recent_bodies, vectors):
        scripts = types.ModuleType("scripts")
        scripts.recall = lambda **kw: [{"created_at": "2026-11-01T00:00:00", "body": b}
                                       for b in recent_bodies]
        monkeypatch.setitem(sys.modules, "scripts", scripts)
        fake = FakeEmbedder(vectors)
        monkeypatch.setattr(ettin_embed, "get_embedder", lambda: fake)
        return fake
    return _install


def test_defaults_are_the_ettin_calibration():
    import inspect
    params = inspect.signature(zd.check_delta).parameters
    assert params["dup_threshold"].default == 0.82
    assert params["delta_threshold"].default == 0.55


def test_no_gemini_or_proxy_dependency():
    src = Path(zd.__file__).read_text()
    assert "embed_batch" not in src and "proxy.env" not in src and "semantic_grep" not in src


@pytest.mark.parametrize("cos,verdict", [(0.83, "duplicate"), (0.70, "delta"), (0.40, "new")])
def test_verdict_bands(setup, cos, verdict):
    old, new = _unit_pair(cos)
    fake = setup(["## Iran\n\nolder facts about the strait"], {"older": old, "newer": new})
    report = zd.check_delta("## Iran\n\nnewer facts about the strait")
    (v,) = report.verdicts
    assert v.verdict == verdict
    assert v.similarity == pytest.approx(cos, abs=1e-3)
    assert len(fake.calls) == 1  # draft and pool embedded in one batch
    if verdict == "duplicate":
        assert "No significant change" in report.delta_text
    else:
        assert "newer facts" in report.delta_text


def test_same_topic_boost_keeps_its_match(setup):
    # Same-topic pool section first at 0.70 (0.73 with the boost), other topic later at 0.71.
    # The old loop compared 0.71 with the raw 0.70 and switched to the other topic.
    draft = np.array([1.0, 0.0, 0.0])
    same = np.array([0.70, np.sqrt(1 - 0.70 ** 2), 0.0])
    other = np.array([0.71, 0.0, np.sqrt(1 - 0.71 ** 2)])
    setup(["## Norway\n\nbudget talks\n\n## Iran\n\nstrait closed"],
          {"continue": draft, "budget": same, "strait": other})
    report = zd.check_delta("## Norway\n\nbudget talks continue")
    (v,) = report.verdicts
    assert v.matched_topic == "Norway"
    assert v.similarity == pytest.approx(0.70, abs=1e-3)


@pytest.mark.skipif(not (ettin_embed.CACHE / "model.onnx").exists(), reason="Ettin package not cached")
def test_real_model_scores_a_restatement_above_a_new_topic():
    m = ettin_embed.get_embedder()
    a = "## UK local elections\n\nReform projected to gain 1,300 seats; Labour to lose half its seats."
    b = "## UK local elections\n\nEve of the vote: Reform projected +1,300 seats, Labour losing half."
    c = "## Space\n\nStarship's next flight targets orbit with 26 Starlink satellites."
    v = m.encode_long([a, b, c])
    assert float(v[0] @ v[1]) > float(v[0] @ v[2]) + 0.2
