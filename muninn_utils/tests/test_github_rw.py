"""Tests for muninn_utils.github_rw — the branch-aware GitHub writer.

The network layer (``_gh``) is the single seam; everything else is orchestration
over it: when to send a blob sha, when to create a branch, how a PR object maps to
a state. Monkeypatch ``_gh`` to a recorder and assert the orchestration, not the
wire format.
"""
from __future__ import annotations

import base64
import urllib.error

import pytest

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


def test_create_branch_returns_existing_ref_on_422(monkeypatch):
    """create_branch is POST-first by design: it does NOT check existence before creating,
    because an existence check immediately before a create can read a stale replica (see
    the docstring — three failures in one session, 2026-07-04). 422 means the branch is
    already there, and the ref is then read back."""
    rec = _Recorder([
        ("GET", "/git/ref/heads/main", {"object": {"sha": "basesha"}}),
        ("POST", "/git/refs", _http_error(422)),
        ("GET", "/git/ref/heads/feat", {"ref": "refs/heads/feat"}),
    ])
    monkeypatch.setattr(gh, "_gh", rec)
    assert gh.create_branch("o/r", "feat") == {"ref": "refs/heads/feat"}
    assert len(rec.posts()) == 1      # the create is attempted, unconditionally


def test_create_branch_rides_out_replica_lag_after_422(monkeypatch):
    """The read-back tolerates brief 404s from an eventually-consistent replica. This is the
    behaviour the POST-first rewrite exists for, and it had no test."""
    reads = iter([_http_error(404), _http_error(404), {"ref": "refs/heads/feat"}])

    def _gh_stub(method, endpoint, body=None, **kw):
        if method == "GET" and "/git/ref/heads/main" in endpoint:
            return {"object": {"sha": "basesha"}}
        if method == "POST":
            raise _http_error(422)
        result = next(reads)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(gh, "_gh", _gh_stub)
    monkeypatch.setattr(gh.time, "sleep", lambda _s: None)
    assert gh.create_branch("o/r", "feat") == {"ref": "refs/heads/feat"}


def test_create_branch_reraises_non_422_errors(monkeypatch):
    rec = _Recorder([
        ("GET", "/git/ref/heads/main", {"object": {"sha": "basesha"}}),
        ("POST", "/git/refs", _http_error(500)),
    ])
    monkeypatch.setattr(gh, "_gh", rec)
    with pytest.raises(urllib.error.HTTPError):
        gh.create_branch("o/r", "feat")


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
        ("GET", "/git/ref/heads/main", {"object": {"sha": "basesha"}}),  # create_branch base
        ("POST", "/git/refs", _http_error(422)),                   # branch already exists
        ("GET", "/git/ref/heads/br", {"ref": "exists"}),           # read-back
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
        ("GET", "/git/ref/heads/main", {"object": {"sha": "basesha"}}),
        ("POST", "/git/refs", _http_error(422)),
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


# --- commit_file refuses to recreate the deleted head of a merged PR (2026-08-29) ---

def _missing_branch_routes(closed_prs):
    return [
        ("GET", "/git/ref/heads/br", _http_error(404)),                 # branch_exists -> False
        ("GET", "/pulls?state=closed&head=o:br", closed_prs),
        ("GET", "/git/ref/heads/main", {"object": {"sha": "basesha"}}),
        ("POST", "/git/refs", {"ref": "created"}),
        ("GET", "/contents/", _http_error(404)),
        ("PUT", "/contents/", {"commit": {"sha": "c3"}}),
    ]


def test_commit_file_missing_branch_with_closed_pr_raises(monkeypatch):
    rec = _Recorder(_missing_branch_routes([{"number": 124}]))
    monkeypatch.setattr(gh, "_gh", rec)
    with pytest.raises(gh.MergedBranchError, match="#124"):
        gh.commit_file("o/r", "f.md", "x", branch="br", message="m")
    assert rec.posts() == [] and rec.puts() == []      # nothing written


def test_commit_file_missing_branch_no_prs_creates(monkeypatch):
    rec = _Recorder(_missing_branch_routes([]))
    monkeypatch.setattr(gh, "_gh", rec)
    gh.commit_file("o/r", "f.md", "x", branch="br", message="m")
    assert len(rec.posts()) == 1 and len(rec.puts()) == 1


def test_commit_file_recreate_bypasses_check(monkeypatch):
    rec = _Recorder(_missing_branch_routes([{"number": 124}]))
    monkeypatch.setattr(gh, "_gh", rec)
    gh.commit_file("o/r", "f.md", "x", branch="br", message="m", recreate=True)
    assert len(rec.puts()) == 1
    assert not any("/pulls?" in c[1] for c in rec.calls)  # check skipped
