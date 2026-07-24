"""github_rw — branch-aware GitHub writes: commit a file, create a branch, open a PR.

The read-only companion is ``gh_status`` (pr_status / issue_status / classify_pr).
The publish flows (``blog_publish``, ``perch_publish``) each privately reimplemented
the same urllib auth + contents dance, all hard-wired to ``main``; this is the
shared, branch-aware writer they should have shared — and the function the
career-search and spoke workflows kept hand-rolling one call at a time.

Auth: ``GH_TOKEN`` or ``GITHUB_TOKEN`` (classic PAT; the header is ``token``, not
``Bearer``). Every request sends ``User-Agent`` (GitHub returns 401 without it)
and retries 502/503 (the cold-start egress-proxy failure; see ops
proxy-503-retry-pattern).

    from muninn_utils import github_rw as gh

    gh.commit_file("oaustegard/career-search", "resume/master.md", text,
                   branch="resume/master", message="update master")
    pr = gh.open_pr("oaustegard/career-search", head="resume/master",
                    title="Current master", body="...")
    gh.pr_state("oaustegard/career-search", pr["number"])   # 'open'

``commit_file`` is the workhorse: it creates the branch from ``base`` if missing,
looks up an existing blob sha so the same call both creates and updates, and
overwrites idempotently. ``pr_state`` reuses ``gh_status.classify_pr`` so the
merged-vs-closed rule lives in exactly one place — call it before pushing to an
existing PR's branch (the mandatory PR STATE CHECK).
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
_UA = "muninn-raven"


def _token():
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")


def _gh(method, endpoint, body=None, *, accept="application/vnd.github+json", raw=False, _retries=3):
    """One GitHub API call. ``endpoint`` may be a path ('/repos/...') or full URL.

    Returns parsed JSON (dict/list), raw text when ``raw=True``, or ``{}`` on an
    empty body. Retries 502/503 with linear backoff; otherwise raises
    ``urllib.error.HTTPError``.
    """
    url = endpoint if endpoint.startswith("http") else API + endpoint
    data = json.dumps(body).encode() if body is not None else None
    headers = {"User-Agent": _UA, "Accept": accept}
    token = _token()
    if token:
        headers["Authorization"] = f"token {token}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    for attempt in range(_retries + 1):
        try:
            with urllib.request.urlopen(req) as resp:
                payload = resp.read()
                if raw:
                    return payload.decode("utf-8")
                return json.loads(payload) if payload else {}
        except urllib.error.HTTPError as e:
            if e.code in (502, 503) and attempt < _retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise
        except urllib.error.URLError:
            if attempt < _retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise


def get_file(repo, path, branch="main"):
    """Return ``(text, sha)`` for a file on ``branch``, or ``(None, None)`` if absent."""
    try:
        data = _gh("GET", f"/repos/{repo}/contents/{path}?ref={branch}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, None
        raise
    return base64.b64decode(data["content"]).decode("utf-8"), data["sha"]


def branch_exists(repo, branch):
    """True iff ``branch`` exists in ``repo``."""
    try:
        _gh("GET", f"/repos/{repo}/git/ref/heads/{branch}")
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def create_branch(repo, branch, base="main"):
    """Create ``branch`` from ``base`` HEAD. If it already exists, return its ref unchanged.

    Race-proof against GitHub's eventually-consistent read replicas (observed
    2026-07-04, three failures in one session): a GET immediately after a
    write may 404, and an existence check immediately before a create may be
    stale. So: POST first and treat 422 ("Reference already exists") as
    success, then fetch the ref tolerating brief 404s.
    """
    base_ref = _gh("GET", f"/repos/{repo}/git/ref/heads/{base}")
    sha = base_ref["object"]["sha"]
    try:
        return _gh("POST", f"/repos/{repo}/git/refs", {"ref": f"refs/heads/{branch}", "sha": sha})
    except urllib.error.HTTPError as e:
        if e.code != 422:
            raise
        # 422 == branch already exists (possibly created milliseconds ago by
        # this same process). Read the ref, riding out replica lag.
        last = None
        for delay in (0.0, 0.5, 1.5, 3.0):
            if delay:
                time.sleep(delay)
            try:
                return _gh("GET", f"/repos/{repo}/git/ref/heads/{branch}")
            except urllib.error.HTTPError as e2:
                if e2.code != 404:
                    raise
                last = e2
        raise last


def commit_file(repo, path, content, *, branch, message, base="main"):
    """Create or update one text file on ``branch``.

    Creates ``branch`` from ``base`` if it doesn't exist, then writes ``content``
    (overwriting if the path already exists on the branch). Returns the
    contents-API response (commit + content metadata).
    """
    create_branch(repo, branch, base)
    _, sha = get_file(repo, path, branch)
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    return _gh("PUT", f"/repos/{repo}/contents/{path}", payload)


def open_pr(repo, *, head, base="main", title, body=""):
    """Open a pull request ``head`` -> ``base``. Returns the API response (html_url, number, ...)."""
    return _gh("POST", f"/repos/{repo}/pulls",
               {"head": head, "base": base, "title": title, "body": body})


def pr_state(repo, number):
    """Live PR state — ``'merged'`` | ``'open'`` | ``'closed'`` — via ``gh_status.classify_pr``.

    Call before pushing to an existing PR's branch (the mandatory PR STATE CHECK):
    a merged PR's branch is orphaned and new commits would sit unshipped.
    """
    from muninn_utils.gh_status import classify_pr
    return classify_pr(_gh("GET", f"/repos/{repo}/pulls/{number}"))
