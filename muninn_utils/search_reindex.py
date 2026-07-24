"""Rebuild and publish the muninn.austegard.com search index in one call.

The site search (muninn-search Worker) reads a BM25+dense index from
Cloudflare KV, which does NOT update on publish: the CI workflow
(.github/workflows/build-search-index.yml) stays dormant until the repo
owner adds the CF_* secrets. Until then, reindexing after every blog/perch/
scratch publish is a mandatory manual step (blog-publishing-trigger, 2026-06-20).

This module collapses that step - previously pip installs + a fresh clone +
a subprocess + a hand-rolled verify - into:

    from muninn_utils.search_reindex import reindex_search
    reindex_search(verify_query="candy from strangers",
                   verify_expect="blog/no-server-at-all")

or, wired into a publish so it runs detached after deploy:

    publish_and_announce(..., reindex=lambda: reindex_search(
        verify_query="<distinctive phrase from the new post>",
        verify_expect="blog/<slug>"))

Requires GH_TOKEN (clone) and CF_ACCOUNT_ID / CF_GATEWAY_ID / CF_API_TOKEN
(KV publish, embeds) in the environment - source GitHub.env and proxy.env
before calling, as with every other credentialed utility.

Verification notes learned the hard way (2026-07-06):
- The worker's response key is ``hits`` (each with a ``chunk_id``), NOT
  ``results``. Parsing the wrong key reports a false miss.
- KV is eventually consistent: a freshly published index can take ~60s to
  serve. A single immediate query is indistinguishable from failure, so
  verification polls with retries instead.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

SITE_REPO = "oaustegard/muninn.austegard.com"
SEARCH_ENDPOINT = "https://muninn-search.austegard.workers.dev/api/search"
_PIP_DEPS = [
    "git+https://github.com/oaustegard/remax_kb.git",
    "bm25s",
    "beautifulsoup4",
    "numpy",
]
# import-name probes for the pip specs above (repo name != module name for remax_kb)
_IMPORT_PROBES = ["remax_kb", "bm25s", "bs4", "numpy"]


def _ensure_deps() -> None:
    """Install the index-builder's dependencies iff any are missing."""
    missing = [p for p in _IMPORT_PROBES if importlib.util.find_spec(p) is None]
    if not missing:
        return
    print(f"  installing index deps (missing: {', '.join(missing)})...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--break-system-packages", "-q", *_PIP_DEPS],
        check=True,
    )


def _fresh_clone(repo: str, workdir: str) -> str:
    """Shallow-clone the site repo so the index sees the just-committed change."""
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN not set - source /mnt/project/GitHub.env first")
    dest = os.path.join(workdir, "site")
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1",
         f"https://x-access-token:{token}@github.com/{repo}.git", dest],
        check=True,
    )
    return dest


def search_hits(query: str, endpoint: str = SEARCH_ENDPOINT) -> list[dict]:
    """POST a query to the search worker and return its ``hits`` list.

    (The response key is ``hits`` - see module docstring.)
    """
    req = urllib.request.Request(
        endpoint,
        data=json.dumps({"query": query}).encode(),
        # the worker 403s the default Python-urllib UA; identify as ours
        headers={"Content-Type": "application/json", "User-Agent": "muninn-raven"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read()).get("hits", [])


def verify_indexed(query: str, expect_substring: str,
                   timeout: int = 120, interval: int = 10) -> bool:
    """Poll the worker until some hit's chunk_id contains ``expect_substring``.

    Retries absorb KV propagation lag (~60s observed); returns False only
    after ``timeout`` seconds of misses.
    """
    deadline = time.time() + timeout
    while True:
        try:
            hits = search_hits(query)
            if any(expect_substring in h.get("chunk_id", "") for h in hits):
                return True
        except Exception as e:  # worker hiccup: retry until deadline
            print(f"  verify poll error (retrying): {e}")
        if time.time() >= deadline:
            return False
        time.sleep(interval)


def reindex_search(repo: str = SITE_REPO,
                   verify_query: str | None = None,
                   verify_expect: str | None = None,
                   verify_timeout: int = 120) -> dict:
    """Clone fresh, rebuild the search index, publish it to KV, optionally verify.

    Returns {"index_version": str|None, "verified": bool|None, "elapsed_s": float}.
    Raises on clone/build/publish failure; a verification miss does NOT raise
    (the index may simply still be propagating) but is reported as
    verified=False for the caller to decide about.
    """
    for var in ("CF_ACCOUNT_ID", "CF_GATEWAY_ID", "CF_API_TOKEN"):
        if not os.environ.get(var):
            raise RuntimeError(f"{var} not set - source /mnt/project/proxy.env first")

    t0 = time.time()
    _ensure_deps()
    with tempfile.TemporaryDirectory() as workdir:
        site = _fresh_clone(repo, workdir)
        proc = subprocess.run(
            [sys.executable, os.path.join(site, "scripts", "publish_index_to_kv.py"),
             "--site-root", site],
            capture_output=True, text=True,
        )
        sys.stdout.write(proc.stdout[-500:])
        if proc.returncode != 0:
            raise RuntimeError(f"publish_index_to_kv failed:\n{proc.stderr[-800:]}")
        m = re.search(r"index-version=(\S+)", proc.stdout)
        version = m.group(1) if m else None

    verified = None
    if verify_query and verify_expect:
        verified = verify_indexed(verify_query, verify_expect, timeout=verify_timeout)
        print(f"  verify: {'FOUND' if verified else 'NOT FOUND after retries'}"
              f" ({verify_expect!r} via {verify_query!r})")

    return {"index_version": version, "verified": verified,
            "elapsed_s": round(time.time() - t0, 1)}
