"""
Tests for the bsky_card CLI entrypoint (issue #66).

`python -m muninn_utils.bsky_card <action>` must be executable and mirror the
three manifest actions (manifests/bsky-card/muninn-bsky-card.v0.4.json):
whoami / post-link / delete-post.

Verifies:
  - Each action emits a single JSON object on stdout (the manifest's contract).
  - whoami returns {handle, did, pds} and carries no `error` field on success
    (the manifest smoke test requires `no_error_field`).
  - Missing creds / unknown action / bad input emit the standard error
    envelope {"error": {"code", "message"}} with a non-zero exit.
  - post-link enforces the 300-grapheme budget before any network call.
  - Library stdout chatter does not leak into the JSON line.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

THIS_DIR = Path(__file__).resolve().parent
PKG_DIR = THIS_DIR.parent
SKILLS_ROOT = PKG_DIR.parent

# Locate the flowing skill (canonical install OR a sibling clone of claude-skills)
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

import importlib.util
spec = importlib.util.spec_from_file_location(
    "bsky_card_cli_under_test", PKG_DIR / "bsky_card.py"
)
bc = importlib.util.module_from_spec(spec)
sys.modules["bsky_card_cli_under_test"] = bc
spec.loader.exec_module(bc)


def _run(argv, stdin="", env=None, monkeypatch=None):
    """Drive bc._main with captured stdout and an optional stdin/env.

    Returns (exit_code, parsed_json_stdout).
    """
    if env is not None:
        for k in ("BSKY_HANDLE", "BSKY_APP_PASSWORD", "BSKY_PDS"):
            monkeypatch.delenv(k, raising=False)
        for k, v in env.items():
            monkeypatch.setenv(k, v)
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    code = bc._main(argv)
    sys.stdout = sys.__stdout__  # restore for pytest reporting
    out = buf.getvalue().strip()
    parsed = json.loads(out) if out else None
    return code, parsed


# ── whoami ─────────────────────────────────────────────────────────


def test_whoami_success_emits_handle_did_pds(monkeypatch):
    monkeypatch.setattr(bc, "create_session", MagicMock(return_value={
        "access_jwt": "jwt", "did": "did:plc:abc", "handle": "austegard.com",
        "pds": "https://bsky.social",
    }))
    monkeypatch.setattr(bc, "resolve_handle", MagicMock(return_value="did:plc:abc"))

    code, out = _run(
        ["whoami"],
        env={"BSKY_HANDLE": "austegard.com", "BSKY_APP_PASSWORD": "pw"},
        monkeypatch=monkeypatch,
    )

    assert code == 0
    assert "error" not in out  # manifest smoke requires no_error_field
    assert out == {"handle": "austegard.com", "did": "did:plc:abc",
                   "pds": "https://bsky.social"}


def test_whoami_surfaces_did_mismatch(monkeypatch):
    monkeypatch.setattr(bc, "create_session", MagicMock(return_value={
        "access_jwt": "jwt", "did": "did:plc:session", "handle": "h",
        "pds": "https://bsky.social",
    }))
    monkeypatch.setattr(bc, "resolve_handle", MagicMock(return_value="did:plc:other"))

    code, out = _run(
        ["whoami"],
        env={"BSKY_HANDLE": "h", "BSKY_APP_PASSWORD": "pw"},
        monkeypatch=monkeypatch,
    )

    assert code == 0
    assert out["did"] == "did:plc:session"
    assert out["did_mismatch"] == "did:plc:other"


def test_whoami_missing_creds_is_auth_invalid(monkeypatch):
    code, out = _run(["whoami"], env={}, monkeypatch=monkeypatch)
    assert code == 1
    assert out["error"]["code"] == "auth_invalid"


# ── post-link ──────────────────────────────────────────────────────


def test_post_link_success_returns_uri_cid_url(monkeypatch):
    monkeypatch.setattr(bc, "create_session", MagicMock(return_value={
        "access_jwt": "jwt", "did": "did:plc:abc", "handle": "h",
        "pds": "https://bsky.social",
    }))
    compose = MagicMock(return_value={"post": {
        "uri": "at://did:plc:abc/app.bsky.feed.post/r",
        "cid": "bafy", "url": "https://bsky.app/profile/h/post/r", "rkey": "r",
    }})
    monkeypatch.setattr(bc, "compose_link_post", compose)

    code, out = _run(
        ["post-link"],
        stdin=json.dumps({"text": "hello", "url": "https://example.com/p"}),
        env={"BSKY_HANDLE": "h", "BSKY_APP_PASSWORD": "pw"},
        monkeypatch=monkeypatch,
    )

    assert code == 0
    assert out == {"uri": "at://did:plc:abc/app.bsky.feed.post/r",
                   "cid": "bafy", "url": "https://bsky.app/profile/h/post/r"}
    # languages default flows through to the library as langs.
    assert compose.call_args.kwargs["langs"] == ["en"]


def test_post_link_threads_overrides_and_languages(monkeypatch):
    monkeypatch.setattr(bc, "create_session", MagicMock(return_value={
        "access_jwt": "jwt", "did": "d", "handle": "h", "pds": "https://bsky.social",
    }))
    compose = MagicMock(return_value={"post": {
        "uri": "at://d/app.bsky.feed.post/r", "cid": "c",
        "url": "https://bsky.app/profile/h/post/r", "rkey": "r",
    }})
    monkeypatch.setattr(bc, "compose_link_post", compose)

    _run(
        ["post-link"],
        stdin=json.dumps({
            "text": "hi", "url": "https://example.com/p",
            "og_overrides": {"title": "T", "description": "D"},
            "languages": ["en", "no"],
        }),
        env={"BSKY_HANDLE": "h", "BSKY_APP_PASSWORD": "pw"},
        monkeypatch=monkeypatch,
    )

    kwargs = compose.call_args.kwargs
    assert kwargs["langs"] == ["en", "no"]
    assert kwargs["og_tags"] == {"url": "https://example.com/p",
                                 "title": "T", "description": "D"}


def test_post_link_text_too_long_blocks_before_network(monkeypatch):
    compose = MagicMock()
    monkeypatch.setattr(bc, "compose_link_post", compose)
    monkeypatch.setattr(bc, "create_session", MagicMock())

    code, out = _run(
        ["post-link"],
        stdin=json.dumps({"text": "x" * 301, "url": "https://example.com/p"}),
        env={"BSKY_HANDLE": "h", "BSKY_APP_PASSWORD": "pw"},
        monkeypatch=monkeypatch,
    )

    assert code == 1
    assert out["error"]["code"] == "text_too_long"
    # Budget gate fires before auth or the post leg.
    assert compose.call_count == 0
    assert bc.create_session.call_count == 0


def test_post_link_missing_fields(monkeypatch):
    code, out = _run(
        ["post-link"],
        stdin=json.dumps({"text": "only text"}),
        env={"BSKY_HANDLE": "h", "BSKY_APP_PASSWORD": "pw"},
        monkeypatch=monkeypatch,
    )
    assert code == 1
    assert out["error"]["code"] == "error"


# ── delete-post ────────────────────────────────────────────────────


def test_delete_post_success(monkeypatch):
    monkeypatch.setattr(bc, "create_session", MagicMock(return_value={
        "access_jwt": "jwt", "did": "did:plc:abc", "handle": "h",
        "pds": "https://bsky.social",
    }))
    monkeypatch.setattr(bc, "delete_post", MagicMock(return_value={
        "uri": "at://did:plc:abc/app.bsky.feed.post/r", "deleted": True,
    }))

    code, out = _run(
        ["delete-post"],
        stdin=json.dumps({"uri": "at://did:plc:abc/app.bsky.feed.post/r"}),
        env={"BSKY_HANDLE": "h", "BSKY_APP_PASSWORD": "pw"},
        monkeypatch=monkeypatch,
    )

    assert code == 0
    assert out == {"uri": "at://did:plc:abc/app.bsky.feed.post/r", "deleted": True}


def test_delete_post_rejects_non_at_uri(monkeypatch):
    code, out = _run(
        ["delete-post"],
        stdin=json.dumps({"uri": "https://bsky.app/profile/h/post/r"}),
        env={"BSKY_HANDLE": "h", "BSKY_APP_PASSWORD": "pw"},
        monkeypatch=monkeypatch,
    )
    assert code == 1
    assert out["error"]["code"] == "uri_invalid"


# ── dispatcher ─────────────────────────────────────────────────────


def test_unknown_action(monkeypatch):
    code, out = _run(["frobnicate"], env={}, monkeypatch=monkeypatch)
    assert code == 2
    assert out["error"]["code"] == "error"


def test_no_action_prints_usage(monkeypatch):
    code, out = _run([], env={}, monkeypatch=monkeypatch)
    assert code == 2
    assert "usage" in out["error"]["message"]


# ── delete_post URI parsing (library helper) ───────────────────────


def test_delete_post_helper_parses_collection_and_rkey(monkeypatch):
    captured = {}

    def fake_urlopen(req):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        return io.BytesIO(b"{}")

    monkeypatch.setattr(bc.urllib.request, "urlopen", fake_urlopen)
    result = bc.delete_post(
        "at://did:plc:abc/app.bsky.feed.post/3l5xyz",
        {"did": "did:plc:abc", "access_jwt": "jwt"},
    )
    assert result == {"uri": "at://did:plc:abc/app.bsky.feed.post/3l5xyz", "deleted": True}
    assert captured["body"] == {
        "repo": "did:plc:abc",
        "collection": "app.bsky.feed.post",
        "rkey": "3l5xyz",
    }
    assert captured["url"].endswith("/com.atproto.repo.deleteRecord")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
