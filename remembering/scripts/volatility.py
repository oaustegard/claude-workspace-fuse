"""Flag memories whose claims go stale, at read time.

The 2026-10-09 memory audit (oaustegard/experiments memory-audit/RESULTS.md)
checked 2,273 present-tense claims against live state: 29% no longer held.
Open items (45% stale), skill versions (44%) and repo state (40%) went stale
fastest, and stale "X is blocked" claims caused wrong refusals. The memory
still read as current, because nothing in it said when it was last true.

`assess()` reads a memory's text and creation time and says which volatile
kinds of claim it makes, when it was last verified, and whether that is longer
ago than the kind's horizon. It is a pure function: no I/O, same answer for
the same input, so the Python skill and the MCP worker (muninn-mcp
src/volatility.ts) can agree on it through shared fixtures
(tests/volatility_fixtures.json).

Read time rather than write time: memories are written by two paths (this
skill straight to Turso, and the MCP worker), and a read-time check covers
every memory already stored with no backfill.

`resolve_refs()` is the optional live half: parallel GitHub REST lookups that
say whether the issues and PRs a memory names are still open. It degrades to None
for anything it cannot resolve; a lookup failure never reads as "open".
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timedelta, timezone

# Days a claim of each kind stays trustworthy without re-checking. Set from the
# audit's stale rates: open items flip fastest (an issue closes in days),
# paths slowest.
HORIZON_DAYS = {
    "open_item": 7,
    "version": 30,
    "capability": 30,
    "env_state": 30,
    "path": 90,
}

DEFAULT_OWNER = "oaustegard"

_REPO = r"[A-Za-z0-9](?:[\w.-]*[A-Za-z0-9_])?"
_PATTERNS = {
    "open_item": re.compile(
        r"\b(?:PRs?|pull requests?|issues?)\s*#\d+[^.\n]{0,60}?\b(?:is|are|remains?|still)\s+(?:open|pending|unmerged|unresolved|in review|awaiting)"
        r"|\b(?:open|pending|unmerged)\s+(?:PRs?|pull requests?|issues?)\b"
        r"|\b(?:PRs?|pull requests?|issues?)\s*#\d+\s*\((?:open|pending)\)"
        r"|\b(?:still|currently|remains?)\s+(?:open|pending|unmerged|unresolved|failing|broken|missing|unfixed)\b"
        r"|\b(?:not\s+yet\s+(?:done|merged|fixed|implemented|shipped|built|in)|awaiting\s+(?:merge|review)|awaits\s+(?:merge|review)|pending\s+(?:merge|review)|blocked\s+on)\b",
        re.IGNORECASE),
    "version": re.compile(
        r"\b(?:is|at|declares|installed|pinned|now)\s+(?:at\s+)?(?:version\s+v?|v)\d+\.\d+(?:\.\d+)?\b"
        r"|\b(?:is|at|declares|installed|pinned|now)\s+(?:at\s+)?\d+\.\d+\.\d+\b"
        r"|\b\d+\.\d+(?:\.\d+)?\s+is\s+installed\b",
        re.IGNORECASE),
    "capability": re.compile(
        r"\b(?:is|are|remains?|gets?|still)\s+(?:blocked|unavailable|inaccessible|unreachable|unsupported|denied|forbidden|broken)\b"
        r"|\b(?:is|are)\s+not\s+(?:available|reachable|accessible|supported|installed|allowed|importable|possible)\b"
        r"|\b(?:cannot|can't|can\s+not)\s+(?:be\s+)?(?:install|reach|access|import|fetch|download|connect|use|push)\w*"
        r"|\b(?:doesn't|does\s+not|don't|do\s+not)\s+work\b|\bno\s+(?:network\s+)?access\s+to\b|\bblocked\s+by\s+(?:the\s+)?(?:egress|proxy|allowlist|firewall)",
        re.IGNORECASE),
    "env_state": re.compile(
        r"\b(?:is|are)\s+(?:installed|preinstalled|importable|reachable|deployed|mounted)\b"
        r"|\bbranch\s+\S+\s+exists\b|\b(?:holds|contains|has)\s+\d+\s+(?:tests?|files?|commits?|sessions?|skills?|memories)\b",
        re.IGNORECASE),
    "path": re.compile(
        r"\b(?:lives|lives\s+at|is\s+at|located\s+at|exists\s+(?:at|in|under))\s+`?(?:~|/|[\w-]+/)[\w./-]+"),
}

KIND_LABEL = {
    "open_item": "open item",
    "version": "version",
    "capability": "availability",
    "env_state": "environment state",
    "path": "path",
}

_AUDIT_HEADER = re.compile(r"\[AUDIT (\d{4}-\d{2}-\d{2})")
_VERIFIED_TAG = re.compile(r"(?:verified|audited)-(\d{4}-\d{2}-\d{2})")
_REF_PATTERNS = (
    re.compile(r"\b(" + _REPO + r")/(" + _REPO + r")#(\d+)"),
    re.compile(r"\b(?:PR|pull request|issue)\s*#(\d+)\s+(?:in|on|of|at)\s+(?:the\s+)?(?:(" + _REPO + r")/)?(" + _REPO + r")",
               re.IGNORECASE),
)
# Shorthand with the owner left out: "remax_kb PR #35", "claude-workspace#222".
_SHORT_REF = (
    re.compile(r"\b(" + _REPO + r")\s+(?:PR|pull request|issue)\s*#(\d+)", re.IGNORECASE),
    re.compile(r"(?<![\w/.-])(" + _REPO + r")#(\d+)"),
)
# Owner-less names must look like this owner's repos: lowercase, no trailing
# punctuation, not a version. Junk that slips through resolves to None.
_SHORT_NAME = re.compile(r"^(?!v?\d)[a-z][a-z0-9_.-]*[a-z0-9]$")
_NOT_REPOS = {"which", "as", "at", "pass", "is", "was", "for", "with", "by", "into", "under", "after", "before",
              "the", "a", "an", "this", "that", "my", "our", "his", "her", "its", "their", "open", "opened",
              "merged", "closed", "draft", "new", "same", "next", "first", "last", "previous", "follow-up",
              "and", "or", "of", "in", "on", "see", "per", "via", "from", "to", "a11y", "upstream", "related"}
# A repo named anywhere in the text: owner/repo, or github.com/owner/repo.
_REPO_MENTION = re.compile(r"(?:github\.com/)?\b(" + _REPO + r")/(" + _REPO + r")\b(?![./]\w)")
_BARE_REF = re.compile(r"(?<![\w/])#(\d{1,6})\b")
_KNOWN_OWNERS = {DEFAULT_OWNER}
SKIP_TAGS = {"news", "news-digest", "digest", "zeitgeist", "session-log", "health"}


def _parse_time(value) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def strip_audit_block(text: str) -> str:
    """The memory without its [AUDIT ...] header and WAS/NOW lines, which record corrections, not claims."""
    lines = (text or "").split("\n")
    i = 0
    while i < len(lines) and (lines[i].startswith(("[AUDIT ", "- WAS:")) or (i and not lines[i].strip())):
        i += 1
    return "\n".join(lines[i:]) if i else (text or "")


def kinds(text: str) -> list[str]:
    """Volatile claim kinds the text makes, in HORIZON_DAYS order."""
    body = strip_audit_block(text)
    return [k for k in HORIZON_DAYS if _PATTERNS[k].search(body)]


def refs(text: str) -> list[str]:
    """`owner/repo#N` for each issue or PR the text names, in order of appearance."""
    text = text or ""
    found: list[tuple[int, str]] = []
    for m in _REF_PATTERNS[0].finditer(text):
        found.append((m.start(), f"{m.group(1)}/{m.group(2)}#{m.group(3)}"))
    for m in _REF_PATTERNS[1].finditer(text):
        found.append((m.start(), f"{m.group(2) or DEFAULT_OWNER}/{m.group(3)}#{m.group(1)}"))
    for i, pat in enumerate(_SHORT_REF):
        for m in pat.finditer(text):
            name = m.group(1)
            # "word PR #N" is often prose ("verify PR #12"); there the name must
            # carry a separator. "name#N" with no space is rarely prose.
            if i == 0 and not re.search(r"[-_.]", name):
                continue
            if _SHORT_NAME.match(name) and name not in _NOT_REPOS:
                found.append((m.start(), f"{DEFAULT_OWNER}/{name}#{m.group(2)}"))
    if not found:
        # Bare "#N" resolves only when the text names exactly one repo of a known owner.
        repos = {f"{o}/{r}" for o, r in _REPO_MENTION.findall(text) if o in _KNOWN_OWNERS}
        if len(repos) == 1:
            repo = repos.pop()
            found = [(m.start(), f"{repo}#{m.group(1)}") for m in _BARE_REF.finditer(text)]
    seen: set[str] = set()
    return [r for _, r in sorted(found) if not (r.lower() in seen or seen.add(r.lower()))]


def verified_at(text: str, created_at, tags=None) -> datetime | None:
    """The latest of the memory's creation, the audit headers in its text, and its
    `verified-YYYY-MM-DD` / `audited-YYYY-MM-DD` tags (memory.mark_verified)."""
    created = _parse_time(created_at)
    stamps = _AUDIT_HEADER.findall(text or "")
    stamps += [m.group(1) for t in (tags or []) if (m := _VERIFIED_TAG.fullmatch(str(t)))]
    dates = [d for d in [created, *(_parse_time(s + "T00:00:00Z") for s in stamps)] if d is not None]
    return max(dates) if dates else None


def assess(text: str, created_at, now: datetime | None = None, tags=None) -> dict | None:
    """Staleness of one memory, or None when it makes no volatile claim and names no issue or PR.

    Returns {"kinds", "refs", "verified_at" (YYYY-MM-DD or None), "stale_kinds",
    "note"}. `stale_kinds` are the kinds whose horizon has passed since
    verified_at; `note` is the one line a reader sees, or None when nothing is
    stale and nothing is an availability claim.
    """
    if tags and SKIP_TAGS.intersection(tags):
        return None  # news digests and logs record what was, not what is
    found = kinds(text)
    named = refs(strip_audit_block(text))
    if not found and not named:
        return None
    now = now or datetime.now(timezone.utc)
    seen = verified_at(text, created_at, tags)
    if seen is None:
        stale = list(found)
    else:
        age = now - seen
        stale = [k for k in found if age > timedelta(days=HORIZON_DAYS[k])]
    return {
        "kinds": found,
        "refs": named,
        "verified_at": seen.strftime("%Y-%m-%d") if seen else None,
        "stale_kinds": stale,
        "note": _note(stale, seen),
    }


def _note(stale: list[str], seen: datetime | None) -> str | None:
    if not stale:
        return None
    since = f"since {seen.strftime('%Y-%m-%d')}" if seen else "(date unknown)"
    labels = ", ".join(KIND_LABEL[k] for k in stale)
    note = f"unverified {since}: {labels}"
    if "capability" in stale:
        note += "; probe before trusting a blocked/unavailable claim"
    return note


def ref_note(states: dict[str, str | None], wanted: list[str]) -> str | None:
    """'now: a/b#1 MERGED, a/b#2 CLOSED' for the refs that are no longer open."""
    changed = [f"{r} {states[r]}" for r in wanted if states.get(r) and states[r] != "OPEN"]
    return f"now: {', '.join(changed)}" if changed else None


# ── live resolution ──

def _state(issue: dict | None) -> str | None:
    """OPEN / CLOSED / MERGED from a REST issue object (a PR is an issue with `pull_request`)."""
    if not isinstance(issue, dict) or issue.get("state") not in ("open", "closed"):
        return None
    if issue["state"] == "open":
        return "OPEN"
    pr = issue.get("pull_request")
    return "MERGED" if isinstance(pr, dict) and pr.get("merged_at") else "CLOSED"


def _gh_issue(ref: str, timeout: float) -> dict | None:
    """GET /repos/{owner}/{repo}/issues/{n} via the gh CLI, else muninn_utils.gh_proxy (claude.ai).

    REST, not GraphQL: the Claude Code on the Web proxy refuses GraphQL
    (probed 2026-10-09).
    """
    repo, num = ref.rsplit("#", 1)
    path = f"repos/{repo}/issues/{int(num)}"
    try:
        out = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=timeout, check=False)
        return json.loads(out.stdout) if out.returncode == 0 else None
    except subprocess.TimeoutExpired:
        return None
    except ValueError:
        return None
    except OSError:
        pass
    try:
        from muninn_utils.gh_proxy import rest
        return rest("/" + path, timeout=int(timeout) or 1)
    except Exception:  # noqa: BLE001 - a lookup failure is "unknown", never "open"
        return None


def resolve_refs(wanted: list[str], *, timeout: float = 4.0, max_refs: int = 25,
                 fetch=None) -> dict[str, str | None]:
    """OPEN / CLOSED / MERGED for each `owner/repo#N`, None where unknown.

    Up to `max_refs` lookups in parallel, all bounded by `timeout` seconds of
    wall clock. `fetch(ref, timeout)` returns the REST issue object or None and
    defaults to the gh CLI.
    """
    from concurrent.futures import ThreadPoolExecutor, wait

    wanted = list(dict.fromkeys(wanted))[:max_refs]
    if not wanted:
        return {}
    fetch = fetch or _gh_issue
    out: dict[str, str | None] = dict.fromkeys(wanted)
    pool = ThreadPoolExecutor(max_workers=min(8, len(wanted)))
    futures = {pool.submit(fetch, ref, timeout): ref for ref in wanted}
    done, _ = wait(futures, timeout=timeout + 1)
    for f in done:
        try:
            out[futures[f]] = _state(f.result())
        except Exception:  # noqa: BLE001, S110 - an unknown state stays None
            pass
    pool.shutdown(wait=False, cancel_futures=True)
    return out
