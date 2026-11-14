"""search_reindex must install what the site's Ettin index build imports, and must not demand the
Gemini gateway variable the index stopped using on 2026-11-05."""
import pytest

from muninn_utils import search_reindex as sr


def test_probes_cover_the_ettin_embedder():
    assert {"onnxruntime", "tokenizers"} <= set(sr._IMPORT_PROBES)
    assert {"onnxruntime", "tokenizers"} <= set(sr._PIP_DEPS)
    assert len(sr._PIP_DEPS) == len(sr._IMPORT_PROBES)


def test_gateway_id_not_required(monkeypatch):
    monkeypatch.setenv("CF_ACCOUNT_ID", "x")
    monkeypatch.setenv("CF_API_TOKEN", "x")
    monkeypatch.delenv("CF_GATEWAY_ID", raising=False)
    reached = []
    monkeypatch.setattr(sr, "_ensure_deps", lambda: reached.append(True) or (_ for _ in ()).throw(RuntimeError("stop")))
    with pytest.raises(RuntimeError, match="stop"):
        sr.reindex_search()
    assert reached, "env check rejected a valid environment before reaching the build"


def test_missing_api_token_still_rejected(monkeypatch):
    monkeypatch.setenv("CF_ACCOUNT_ID", "x")
    monkeypatch.delenv("CF_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="CF_API_TOKEN"):
        sr.reindex_search()


def test_clone_keeps_the_token_out_of_argv(monkeypatch, tmp_path):
    secret = "ghp_" + "t0k3n" * 6
    monkeypatch.setenv("GH_TOKEN", secret)
    seen = []
    monkeypatch.setattr(sr.subprocess, "run", lambda argv, **kw: seen.append(argv))
    sr._fresh_clone("oaustegard/muninn.austegard.com", str(tmp_path))
    (argv,) = seen
    assert not any(secret in a for a in argv)
    assert "https://github.com/oaustegard/muninn.austegard.com.git" in argv
    assert any(a.startswith("credential.helper=") and "$GH_TOKEN" in a for a in argv)
