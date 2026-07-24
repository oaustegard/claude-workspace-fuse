"""gh_status — freshly-fetched GitHub PR/issue state for summary lines.

A forcing function against stale-state assertions. The recurring mistake is
hand-typing "PR #N is open" in a summary from memory of what was true earlier;
it goes stale the moment the PR is merged. Generate the line instead:

    from muninn_utils.gh_status import status_line
    print(status_line("oaustegard/muninn-utilities", 62))   # always live

classify_pr / classify_issue are pure (the interesting logic — a merged PR has
state "closed" but should report "merged") and are unit-tested. pr_status /
issue_status are thin fetch wrappers.
"""
from __future__ import annotations

import json
import os
import urllib.request


def classify_pr(data: dict) -> str:
    """Map a GitHub pulls API object to a state string: merged|open|closed."""
    if data.get("merged"):
        return "merged"
    return data.get("state", "unknown")


def classify_issue(data: dict) -> str:
    """Map a GitHub issues API object to a state string: open|closed."""
    return data.get("state", "unknown")


def _gh_token():
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")


def _gh_get(endpoint: str) -> dict:
    headers = {"User-Agent": "muninn-raven", "Accept": "application/vnd.github+json"}
    token = _gh_token()
    if token:
        headers["Authorization"] = f"token {token}"
    url = f"https://api.github.com{endpoint}"
    req = urllib.request.Request(url, headers=headers)
    return json.loads(urllib.request.urlopen(req, timeout=20).read())


def pr_status(repo: str, number: int) -> str:
    """Live PR state. repo is 'owner/name'."""
    return classify_pr(_gh_get(f"/repos/{repo}/pulls/{number}"))


def issue_status(repo: str, number: int) -> str:
    """Live issue state. repo is 'owner/name'."""
    return classify_issue(_gh_get(f"/repos/{repo}/issues/{number}"))


def status_line(repo: str, number: int, kind: str = "pr") -> str:
    """A freshly-fetched one-liner for summaries: 'owner/repo#N: merged'."""
    state = pr_status(repo, number) if kind == "pr" else issue_status(repo, number)
    return f"{repo}#{number}: {state}"
