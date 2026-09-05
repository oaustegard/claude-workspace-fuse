"""
Tests for bsky_card.like / unlike.

A like is the lightest acknowledgment Muninn can send. These verify the
app.bsky.feed.like record is well-formed (subject uri+cid, $type, createdAt),
that the correct endpoint/collection are hit, and that unlike deletes by rkey.
"""
from __future__ import annotations

import json
import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

THIS_DIR = Path(__file__).resolve().parent
PKG_DIR = THIS_DIR.parent
SKILLS_ROOT = PKG_DIR.parent

# Locate the flowing skill (bsky_card imports it at module load)
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
    "bsky_card_under_test_like", PKG_DIR / "bsky_card.py"
)
bc = importlib.util.module_from_spec(spec)
sys.modules["bsky_card_under_test_like"] = bc
spec.loader.exec_module(bc)

AUTH = {"did": "did:plc:muninn", "access_jwt": "jwt-token", "handle": "muninn.austegard.com"}
SUBJ_URI = "at://did:plc:other/app.bsky.feed.post/abc123"
SUBJ_CID = "bafyreiexamplecid"


def _capture(monkeypatch, response):
    """Patch urlopen; capture the urllib Request that was sent."""
    captured = {}

    def fake_urlopen(req, *a, **k):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        captured["body"] = json.loads(req.data.decode()) if req.data else None
        m = MagicMock()
        m.read.return_value = json.dumps(response).encode()
        return m

    monkeypatch.setattr(bc.urllib.request, "urlopen", fake_urlopen)
    return captured


def test_like_builds_valid_record(monkeypatch):
    cap = _capture(monkeypatch, {
        "uri": "at://did:plc:muninn/app.bsky.feed.like/like789",
        "cid": "bafyreilikecid",
    })
    out = bc.like(SUBJ_URI, SUBJ_CID, AUTH)

    # endpoint + collection
    assert cap["url"].endswith("/com.atproto.repo.createRecord")
    assert cap["method"] == "POST"
    assert cap["body"]["collection"] == "app.bsky.feed.like"
    assert cap["body"]["repo"] == AUTH["did"]

    # record shape: subject pins both uri and cid; type + timestamp present
    rec = cap["body"]["record"]
    assert rec["$type"] == "app.bsky.feed.like"
    assert rec["subject"] == {"uri": SUBJ_URI, "cid": SUBJ_CID}
    assert rec["createdAt"].endswith("Z")

    # auth header carries the bearer jwt
    assert cap["headers"]["authorization"] == "Bearer jwt-token"

    # returns the like record's own identifiers
    assert out["uri"].endswith("/like789")
    assert out["rkey"] == "like789"
    assert out["cid"] == "bafyreilikecid"


def test_unlike_deletes_by_rkey(monkeypatch):
    cap = _capture(monkeypatch, {})
    like_uri = "at://did:plc:muninn/app.bsky.feed.like/like789"
    out = bc.unlike(like_uri, AUTH)

    assert cap["url"].endswith("/com.atproto.repo.deleteRecord")
    assert cap["body"]["collection"] == "app.bsky.feed.like"
    assert cap["body"]["rkey"] == "like789"
    assert cap["body"]["repo"] == AUTH["did"]
    assert out == {"deleted": like_uri}
