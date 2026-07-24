"""
news_watch.py — Watch claude.com/blog for new posts during Daily Perch.

Pure parsing + state. HTTP fetching is delegated to the caller's web_fetch
tool because claude.com WAFs raw HTTP from container egress (verified
2026-05-14 — 403 on /blog, /feed.xml, /atom.xml, /rss.xml via both curl and
httpx, with browser UA). The model's web_fetch tool gets through.

Usage from a task file:
    from muninn_utils.news_watch import (
        parse_claude_blog, filter_new, get_last_seen, set_last_seen,
        format_for_report, BLOG_URL,
    )

    # 1. web_fetch(BLOG_URL) returns the rendered markdown/text
    # 2. posts = parse_claude_blog(fetched)
    # 3. new = filter_new(posts, last_seen=get_last_seen())
    # 4. format and emit new posts into the report
    # 5. set_last_seen(posts[0]['date']) — newest date on page

Design notes:
  - First run (last_seen is None) returns no new posts — seeds state without
    alerting on already-historical content.
  - Watermark advances even when no new posts found, so we don't re-scan
    the same back-window every day.
  - State lives in Turso config (key 'claude-blog-last-seen-iso', category 'ops').
"""
import re
from datetime import date
from typing import Optional

STATE_KEY = "claude-blog-last-seen-iso"
BLOG_URL = "https://claude.com/blog"

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

# Known categories on claude.com/blog (used to extract category labels that
# appear as standalone lines near a post card). Add new ones as they appear.
_CATEGORIES = {
    "Agents", "Claude Code", "Enterprise AI", "Product announcements",
    "Claude Security", "Claude Cowork", "Claude Enterprise", "Claude apps",
    "Claude Platform",
}


def parse_claude_blog(content: str) -> list[dict]:
    """Extract blog posts from claude.com/blog index content.

    Works on both markdown-extracted output (what web_fetch returns) and
    raw HTML (the regex shape matches either).

    Returns list of {url, title, date (YYYY-MM-DD or None), category} dicts,
    de-duplicated by URL, sorted newest-first by date.
    """
    posts = {}
    # Anchor on links to /blog/<slug> (deterministic). The title is the
    # link text; the date and category appear nearby in the surrounding
    # markup.
    link_re = re.compile(
        r'\[([^\]]+)\]\((https://claude\.com/blog/[a-z0-9][a-z0-9-]+)\)'
    )
    date_re = re.compile(
        r'\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|'
        r'Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2}),\s+(\d{4})\b'
    )
    for m in link_re.finditer(content):
        title, url = m.group(1).strip(), m.group(2)
        if url in posts:
            continue
        if '/blog/category/' in url:  # category index links, not posts
            continue
        if url.rstrip('/').endswith('/blog'):  # self-link
            continue
        # The nearest date BEFORE the link is the post's date.
        back = content[max(0, m.start() - 600):m.start()]
        last_date = None
        for dm in date_re.finditer(back):
            last_date = dm  # keep the latest (closest to link)
        iso = _date_to_iso(last_date) if last_date else None
        category = _extract_category(back)
        posts[url] = {
            "url": url,
            "title": title,
            "date": iso,
            "category": category,
        }
    out = [p for p in posts.values() if p["date"]]
    out.sort(key=lambda p: p["date"], reverse=True)
    return out


def _date_to_iso(dmatch) -> Optional[str]:
    mon_abbr = dmatch.group(1)[:3].lower()
    day = int(dmatch.group(2))
    year = int(dmatch.group(3))
    mon_n = _MONTHS.get(mon_abbr)
    if not mon_n:
        return None
    try:
        return date(year, mon_n, day).isoformat()
    except ValueError:
        return None


def _extract_category(back: str) -> Optional[str]:
    for line in reversed(back.splitlines()):
        stripped = line.strip()
        if stripped in _CATEGORIES:
            return stripped
    return None


def filter_new(posts: list[dict], last_seen: Optional[str]) -> list[dict]:
    """Return posts strictly newer than last_seen.

    last_seen=None (first run) returns an empty list — first run seeds
    state without alerting on existing content. Caller still advances
    set_last_seen so the second run reports anything published in between.
    """
    if not posts or last_seen is None:
        return []
    return [p for p in posts if p["date"] and p["date"] > last_seen]


def get_last_seen(key: str = STATE_KEY) -> Optional[str]:
    """Read the last-seen ISO date from Turso config. None if unset."""
    try:
        from scripts import config_get
        v = config_get(key)
        return v.strip() if v else None
    except Exception:
        return None


def set_last_seen(iso: str, key: str = STATE_KEY) -> None:
    """Write last-seen ISO date to config under category 'ops'."""
    from scripts import config_set
    config_set(key, iso, "ops")


def format_for_report(new_posts: list[dict]) -> str:
    """Render new posts as HTML <li> rows for the calendar-event report.

    Returns inner HTML (no <ul> wrapper) so callers can omit the entire
    section when there are no new posts — silence is the signal.

    Each row: <li><a href=URL>Title</a> <em>(Category)</em> — DATE</li>
    The task file is expected to replace "— DATE" with a one-sentence
    summary derived from a follow-up fetch of the post URL.
    """
    if not new_posts:
        return ""
    rows = []
    for p in new_posts:
        cat = f' <em>({_esc(p["category"])})</em>' if p.get("category") else ""
        title = _esc(p["title"] or "")
        rows.append(f'  <li><a href="{p["url"]}">{title}</a>{cat} — {p["date"]}</li>')
    return "\n".join(rows)


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))
