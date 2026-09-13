"""Tests for muninn_utils.gh_status.

gh_status is a forcing function against stale-state assertions: instead of
hand-typing "PR #N is open" from memory in a summary (which goes stale the moment
a PR is merged), call status_line()/pr_status(), which fetch live. The classify_*
functions are pure and tested here; the network wrappers are thin.
"""
from __future__ import annotations

import muninn_utils.gh_status as gh


def test_classify_pr_merged_beats_state():
    # a merged PR has state=closed but should report "merged"
    assert gh.classify_pr({"merged": True, "state": "closed"}) == "merged"


def test_classify_pr_open():
    assert gh.classify_pr({"merged": False, "state": "open"}) == "open"


def test_classify_pr_closed_unmerged():
    assert gh.classify_pr({"merged": False, "state": "closed"}) == "closed"


def test_classify_issue():
    assert gh.classify_issue({"state": "open"}) == "open"
    assert gh.classify_issue({"state": "closed"}) == "closed"


def test_status_line_uses_fresh_fetch(monkeypatch):
    # status_line must derive state from a live fetch, never a passed-in guess
    monkeypatch.setattr(gh, "pr_status", lambda repo, number: "merged")
    assert gh.status_line("oaustegard/muninn-utilities", 62) == "oaustegard/muninn-utilities#62: merged"


def test_status_line_issue_kind(monkeypatch):
    monkeypatch.setattr(gh, "issue_status", lambda repo, number: "closed")
    assert gh.status_line("o/r", 5, kind="issue") == "o/r#5: closed"
