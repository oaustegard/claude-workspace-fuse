"""Tests for muninn_utils.perch_triage comment routing.

Regression for discussion #331: an Oskar comment on an unreacted flight log was
fetched into `odin_comments` and never read, so the request went unanswered.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from muninn_utils import perch_triage as pt

OLD = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat().replace("+00:00", "Z")


def comment(body, when, login="oaustegard"):
    return {"author": {"login": login}, "body": body, "createdAt": when}


def node(number, comments=(), reactions=None, closed=False):
    groups = [
        {"content": k, "reactors": {"totalCount": v}}
        for k, v in (reactions or {}).items()
    ]
    return {
        "id": f"D_{number}", "number": number, "title": f"Fly {number}",
        "closed": closed, "createdAt": OLD, "updatedAt": OLD, "body": "x",
        "reactionGroups": groups, "comments": {"nodes": list(comments)},
    }


@pytest.fixture
def gh(monkeypatch):
    calls = []
    discussions = []

    def fake(query, variables=None):
        calls.append((query, variables))
        if "addDiscussionComment" in query:
            return {"addDiscussionComment": {"comment": {"id": "C", "url": "u"}}}
        if "closeDiscussion" in query:
            return {"closeDiscussion": {"discussion": {"id": "D", "closed": True}}}
        return {"repository": {"discussions": {"nodes": discussions}}}

    monkeypatch.setattr(pt, "_gh_graphql", fake)
    fake.calls = calls
    fake.discussions = discussions
    return fake


def test_unanswered_comment_surfaces(gh):
    gh.discussions.append(node(331, [comment("You should explore this", "2026-09-09T12:43:01Z")]))
    logs = pt.fetch_open_logs()
    assert [c["body"] for c in logs[0]["unanswered"]] == ["You should explore this"]
    result = pt.triage(logs)
    assert [l["number"] for l in result["respond"]] == [331]
    assert result["nag"] == []
    assert "You should explore this" in pt.triage_report(result)


def test_marked_reply_answers_earlier_comments(gh):
    gh.discussions.append(node(1, [
        comment("question", "2026-09-01T00:00:00Z"),
        comment(f"answer\n\n{pt.MUNINN_MARKER}", "2026-09-02T00:00:00Z"),
    ]))
    log = pt.fetch_open_logs()[0]
    assert log["unanswered"] == []
    assert log["odin_comments"] == [log["odin_comments"][0]]
    assert log["odin_comments"][0]["body"] == "question"


def test_comment_after_reply_resurfaces(gh):
    gh.discussions.append(node(1, [
        comment("q1", "2026-09-01T00:00:00Z"),
        comment(f"a1 {pt.MUNINN_MARKER}", "2026-09-02T00:00:00Z"),
        comment("q2", "2026-09-03T00:00:00Z"),
    ]))
    assert [c["body"] for c in pt.fetch_open_logs()[0]["unanswered"]] == ["q2"]


def test_other_authors_ignored(gh):
    gh.discussions.append(node(1, [comment("drive-by", "2026-09-01T00:00:00Z", login="someone")]))
    assert pt.fetch_open_logs()[0]["unanswered"] == []


def test_comment_blocks_auto_close(gh, monkeypatch):
    monkeypatch.setitem(sys.modules, "scripts", None)  # remember() must not be reached
    gh.discussions.append(node(2, [comment("but also do X", "2026-09-01T00:00:00Z")],
                               reactions={"THUMBS_UP": 1}))
    result = pt.triage(pt.fetch_open_logs())
    assert [l["number"] for l in result["respond"]] == [2]
    assert result["auto_closed"] == []
    assert not any("closeDiscussion" in q for q, _ in gh.calls)


def test_reply_appends_marker_once(gh):
    pt.reply("D_1", "hello")
    pt.reply("D_1", f"already {pt.MUNINN_MARKER}")
    bodies = [v["body"] for q, v in gh.calls if "addDiscussionComment" in q]
    assert bodies[0].endswith(pt.MUNINN_MARKER)
    assert bodies[1].count(pt.MUNINN_MARKER) == 1


def test_pending_comments_filters(gh):
    gh.discussions.extend([
        node(1, [comment("ask", "2026-09-01T00:00:00Z")]),
        node(2),
        node(3, [comment("closed ask", "2026-09-01T00:00:00Z")], closed=True),
    ])
    assert [l["number"] for l in pt.pending_comments()] == [1]
