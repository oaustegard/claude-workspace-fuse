"""Tests for bsky_moderation (two-stage thread moderation).

All network is mocked — verifies:
  - _ensure_post_uri parses bsky.app URLs and passes at:// URIs through
  - extract_thread_repliers flattens the reply tree, dedups by DID, joins a
    poster's multiple texts, and excludes the root author + authed self
  - moderate(dry_run=True) writes nothing and returns DRY_RUN rows
  - moderate(dry_run=False) emits the correct mute / block request bodies
  - transient 5xx/429 responses are retried and recovered
  - missing credentials raise on a real (non-dry-run) call
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "bsky_moderation_under_test", PKG_DIR / "bsky_moderation.py"
)
M = importlib.util.module_from_spec(spec)
sys.modules["bsky_moderation_under_test"] = M
spec.loader.exec_module(M)


class _Resp:
    def __init__(self, code, payload=None):
        self.status_code = code
        self._payload = payload or {}
        self.content = b"{}"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise M.requests.HTTPError(str(self.status_code))

    def json(self):
        return self._payload


def _fake_session(monkeypatch, did="did:plc:me"):
    monkeypatch.setattr(M, "_get_session",
                        lambda: {"accessJwt": "jwt", "did": did, "_at": 1e12})


# ---------- URI parsing ----------
def test_ensure_post_uri_passthrough():
    uri = "at://did:plc:abc/app.bsky.feed.post/xyz"
    assert M._ensure_post_uri(uri) == uri


def test_ensure_post_uri_from_url(monkeypatch):
    monkeypatch.setattr(M, "_resolve_handle", lambda h: "did:plc:root")
    got = M._ensure_post_uri("https://bsky.app/profile/holden.bsky.social/post/rk1")
    assert got == "at://did:plc:root/app.bsky.feed.post/rk1"


# ---------- Utility 1 ----------
def test_extract_flatten_dedup_and_exclusions(monkeypatch):
    thread = {
        "post": {"author": {"did": "did:plc:root"}},
        "replies": [
            {"post": {"author": {"did": "did:plc:a", "handle": "a.test"},
                      "record": {"text": "first"}},
             "replies": [
                 {"post": {"author": {"did": "did:plc:a", "handle": "a.test"},
                           "record": {"text": "again"}}, "replies": []},
                 {"post": {"author": {"did": "did:plc:me", "handle": "me.test"},
                           "record": {"text": "my own reply"}}, "replies": []},
             ]},
            {"post": {"author": {"did": "did:plc:root", "handle": "root.test"},
                      "record": {"text": "root self-reply"}}, "replies": []},
        ],
    }
    monkeypatch.setattr(M, "_ensure_post_uri", lambda x: "at://uri")
    monkeypatch.setattr(M, "_get_session", lambda: {"did": "did:plc:me"})
    monkeypatch.setattr(M.requests, "get",
                        lambda *a, **k: _Resp(200, {"thread": thread}))

    out = M.extract_thread_repliers("http://x")
    assert len(out) == 1                       # root + self excluded
    assert out[0]["did"] == "did:plc:a"
    assert out[0]["text"] == "first \u23ce again"   # joined


# ---------- Utility 2 ----------
def test_dry_run_writes_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr(M.requests, "post",
                        lambda *a, **k: calls.append(a) or _Resp(200))
    res = M.moderate({"did:plc:x": "mute", "did:plc:y": "block"}, dry_run=True)
    assert calls == []
    assert {r["result"] for r in res} == {"DRY_RUN"}


def test_moderate_emits_correct_bodies(monkeypatch):
    _fake_session(monkeypatch)
    sent = []

    def fake_post(url, headers=None, json=None, timeout=None):
        sent.append((url, json))
        return _Resp(200, {"uri": "at://blk"})

    monkeypatch.setattr(M.requests, "post", fake_post)
    res = M.moderate({"did:plc:t1": "mute", "did:plc:t2": "block"},
                     dry_run=False, max_workers=2)
    assert all(not str(r["result"]).startswith("ERROR") for r in res)

    mute = next(b for u, b in sent if u.endswith("muteActor"))
    block = next(b for u, b in sent if u.endswith("createRecord"))
    assert mute == {"actor": "did:plc:t1"}
    assert block["collection"] == "app.bsky.graph.block"
    assert block["record"]["subject"] == "did:plc:t2"
    assert block["record"]["$type"] == "app.bsky.graph.block"
    assert block["repo"] == "did:plc:me"


def test_transient_is_retried(monkeypatch):
    seq = {"n": 0}

    def flaky_post(url, headers=None, json=None, timeout=None):
        seq["n"] += 1
        return _Resp(502) if seq["n"] == 1 else _Resp(200, {"uri": "ok"})

    monkeypatch.setattr(M.requests, "post", flaky_post)
    monkeypatch.setattr(M.time, "sleep", lambda *_: None)
    out = M._post_with_retry("app.bsky.graph.muteActor", "jwt", {"actor": "d"})
    assert out == {"uri": "ok"}
    assert seq["n"] == 2


def test_missing_creds_raises(monkeypatch):
    monkeypatch.setattr(M, "_get_session", lambda: None)
    try:
        M.moderate({"did:plc:x": "mute"}, dry_run=False)
    except RuntimeError as e:
        assert "not authenticated" in str(e)
    else:
        raise AssertionError("expected RuntimeError on missing creds")
