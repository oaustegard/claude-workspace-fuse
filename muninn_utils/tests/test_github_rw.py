"""Tests for muninn_utils.github_rw — the branch-aware GitHub writer.

The network layer (``_gh``) is the single seam; everything else is orchestration
over it: when to send a blob sha, when to create a branch, how a PR object maps to
a state. Monkeypatch ``_gh`` to a recorder and assert the orchestration, not the
wire format.
"""
from __future__ import annotations

import base64
import urllib.error

import muninn_utils.github_rw as gh


class _Recorder:
    """Stand-in for ``_gh``: returns scripted responses keyed by (method, endpoint
    substring) and records every call. A scripted value that is an Exception is
    raised, to simulate HTTP errors."""

    def __init__(self, routes):
        self.routes = routes          # list of (method, substr, response_or_exception)
        self.calls = []

    def __call__(self, method, endpoint, body=None, **kw):
        self.calls.append((method, endpoint, body))
        for m, sub, resp in self.routes:
            if m == method and sub in endpoint:
                if isinstance(resp, Exception):
                    raise resp
                return resp
        raise AssertionError(f"unrouted call: {method} {endpoint}")

    def posts(self):
        return [c for c in self.calls if c[0] == "POST"]

    def puts(self):
        return [c for c in self.calls if c[0] == "PUT"]


def _http_error(code):
    return urllib.error.HTTPError("https://api.github.com", code, "msg", {}, None)


def test_get_file_returns_text_and_sha(monkeypatch):
    content = base64.b64encode(b"hello").decode()
    monkeypatch.setattr(gh, "_gh", _Recorder([("GET", "/contents/", {"content": content, "sha": "abc"})]))
    assert gh.get_file("o/r", "f.md") == ("hello", "abc")


def test_get_file_absent_returns_none(monkeypatch):
    monkeypatch.setattr(gh, "_gh", _Recorder([("GET", "/contents/", _http_error(404))]))
    assert gh.get_file("o/r", "missing.md") == (None, None)


def test_get_file_propagates_non_404(monkeypatch):
    monkeypatch.setattr(gh, "_gh", _Recorder([("GET", "/contents/", _http_error(500))]))
    try:
        gh.get_file("o/r", "f.md")
        assert False, "expected HTTPError to propagate"
    except urllib.error.HTTPError as e:
        assert e.code == 500


def test_branch_exists_true(monkeypatch):
    monkeypatch.setattr(gh, "_gh", _Recorder([("GET", "/git/ref/heads/", {"ref": "x"})]))
    assert gh.branch_exists("o/r", "feat") is True


def test_branch_exists_false_on_404(monkeypatch):
    monkeypatch.setattr(gh, "_gh", _Recorder([("GET", "/git/ref/heads/", _http_error(404))]))
    assert gh.branch_exists("o/r", "feat") is False


def test_create_branch_noop_when_exists(monkeypatch):
    rec = _Recorder([("GET", "/git/ref/heads/feat", {"ref": "refs/heads/feat"})])
    monkeypatch.setattr(gh, "_gh", rec)
    gh.create_branch("o/r", "feat")
    assert rec.posts() == []          # never creates a ref when the branch is there


def test_create_branch_creates_from_base(monkeypatch):
    rec = _Recorder([
        ("GET", "/git/ref/heads/feat", _http_error(404)),          # branch_exists -> no
        ("GET", "/git/ref/heads/main", {"object": {"sha": "basesha"}}),
        ("POST", "/git/refs", {"ref": "refs/heads/feat"}),
    ])
    monkeypatch.setattr(gh, "_gh", rec)
    gh.create_branch("o/r", "feat", base="main")
    assert rec.posts()[0][2] == {"ref": "refs/heads/feat", "sha": "basesha"}


def test_commit_file_new_omits_sha(monkeypatch):
    rec = _Recorder([
        ("GET", "/git/ref/heads/br", {"ref": "exists"}),           # create_branch no-op
        ("GET", "/contents/", _http_error(404)),                   # get_file -> absent
        ("PUT", "/contents/", {"commit": {"sha": "c1"}}),
    ])
    monkeypatch.setattr(gh, "_gh", rec)
    gh.commit_file("o/r", "new.md", "body", branch="br", message="m")
    put = rec.puts()[0]
    assert "sha" not in put[2]
    assert base64.b64decode(put[2]["content"]).decode() == "body"
    assert put[2]["branch"] == "br"


def test_commit_file_existing_includes_sha(monkeypatch):
    existing = base64.b64encode(b"old").decode()
    rec = _Recorder([
        ("GET", "/git/ref/heads/br", {"ref": "exists"}),
        ("GET", "/contents/", {"content": existing, "sha": "filesha"}),
        ("PUT", "/contents/", {"commit": {"sha": "c2"}}),
    ])
    monkeypatch.setattr(gh, "_gh", rec)
    gh.commit_file("o/r", "old.md", "new", branch="br", message="m")
    assert rec.puts()[0][2]["sha"] == "filesha"


def test_open_pr_passthrough(monkeypatch):
    rec = _Recorder([("POST", "/pulls", {"number": 7, "html_url": "u"})])
    monkeypatch.setattr(gh, "_gh", rec)
    out = gh.open_pr("o/r", head="feat", title="T", body="B")
    assert out["number"] == 7
    assert rec.posts()[0][2] == {"head": "feat", "base": "main", "title": "T", "body": "B"}


def test_pr_state_maps_merged(monkeypatch):
    monkeypatch.setattr(gh, "_gh", _Recorder([("GET", "/pulls/9", {"merged": True, "state": "closed"})]))
    assert gh.pr_state("o/r", 9) == "merged"


def test_pr_state_open(monkeypatch):
    monkeypatch.setattr(gh, "_gh", _Recorder([("GET", "/pulls/9", {"merged": False, "state": "open"})]))
    assert gh.pr_state("o/r", 9) == "open"
