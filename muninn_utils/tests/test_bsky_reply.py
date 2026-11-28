"""
Tests for bsky_card.reply_refs and create_post's reply rebuild.

A reply's root must be the thread root, not the parent, when the parent is
itself a reply; otherwise the app-view drops the reply from the thread.
"""
from __future__ import annotations

import json
import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

THIS_DIR = Path(__file__).resolve().parent
PKG_DIR = THIS_DIR.parent
SKILLS_ROOT = PKG_DIR.parent

import os as _os
for _flow_path in (
    "/mnt/skills/user/flowing/scripts",
    str(SKILLS_ROOT / "flowing" / "scripts"),
    str(PKG_DIR.parent.parent / "claude-skills" / "flowing" / "scripts"),
):
    if _os.path.isdir(_flow_path):
        sys.path.insert(0, _flow_path)
        break
else:
    raise RuntimeError("flowing skill not found in any expected location")
import flowing as _flowing
sys.modules.setdefault("flowing", _flowing)

spec = importlib.util.spec_from_file_location(
    "bsky_card_under_test_reply", PKG_DIR / "bsky_card.py"
)
bc = importlib.util.module_from_spec(spec)
sys.modules["bsky_card_under_test_reply"] = bc
spec.loader.exec_module(bc)

AUTH = {"did": "did:plc:muninn", "access_jwt": "jwt-token", "handle": "muninn.austegard.com"}
ROOT = {"uri": "at://did:plc:a/app.bsky.feed.post/root", "cid": "cid-root"}
MID = {"uri": "at://did:plc:b/app.bsky.feed.post/mid", "cid": "cid-mid"}
POSTS = {
    ROOT["uri"]: {**ROOT, "record": {"text": "top"}},
    MID["uri"]: {**MID, "record": {"text": "reply", "reply": {"root": ROOT, "parent": ROOT}}},
}


def _fake(monkeypatch):
    sent = []

    def fake_urlopen(req, *a, **k):
        url = req if isinstance(req, str) else req.full_url
        m = MagicMock()
        if "getPosts" in url:
            from urllib.parse import unquote
            uri = unquote(url.split("uris=", 1)[1])
            m.read.return_value = json.dumps({"posts": [POSTS[uri]] if uri in POSTS else []}).encode()
        else:
            sent.append(json.loads(req.data.decode()))
            m.read.return_value = json.dumps(
                {"uri": "at://did:plc:muninn/app.bsky.feed.post/new", "cid": "cid-new"}).encode()
        return m

    monkeypatch.setattr(bc.urllib.request, "urlopen", fake_urlopen)
    return sent


def test_reply_to_top_level_post_uses_it_as_root(monkeypatch):
    _fake(monkeypatch)
    assert bc.reply_refs(ROOT["uri"]) == {"root": ROOT, "parent": ROOT}


def test_reply_to_a_reply_uses_the_thread_root(monkeypatch):
    _fake(monkeypatch)
    assert bc.reply_refs(MID["uri"]) == {"root": ROOT, "parent": MID}


def test_create_post_repairs_a_hand_built_root(monkeypatch):
    sent = _fake(monkeypatch)
    rec = {"$type": "app.bsky.feed.post", "text": "hi", "createdAt": "2026-11-23T00:00:00Z",
           "reply": {"root": MID, "parent": MID}}
    bc.create_post(rec, AUTH)
    assert sent[0]["record"]["reply"] == {"root": ROOT, "parent": MID}
    assert rec["reply"] == {"root": MID, "parent": MID}  # caller's dict untouched


def test_reply_to_missing_post_is_refused(monkeypatch):
    sent = _fake(monkeypatch)
    rec = {"text": "x", "reply": {"parent": {"uri": "at://did:plc:a/app.bsky.feed.post/gone", "cid": "c"}}}
    with pytest.raises(ValueError, match="post not found"):
        bc.create_post(rec, AUTH)
    assert sent == []
