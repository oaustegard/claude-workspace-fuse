"""
perch_publish.py — Publish perch flight logs to muninn.austegard.com/perch/

Converts GitHub discussion markdown to HTML, pushes to GitHub Pages,
updates index and Atom feed.

Usage:
    from perch_publish import create_flight_log, publish_flight_log
    disc = create_flight_log(title, body)   # -> {number, url, id}; always lands in mac
    result = publish_flight_log(430)
    # → {"url": "https://muninn.austegard.com/perch/...", "slug": "...", "commit_sha": "..."}
"""
import markdown
import re
import json
import os
import urllib.request
import urllib.error
from html import escape, unescape
from datetime import datetime, timezone

REPO = "oaustegard/muninn.austegard.com"
SITE_BASE = "https://muninn.austegard.com"

# Flight-log discussion target — HARD-PINNED to the mac repo. claude-skills is the
# RETIRED flight-log home; creating discussions there is the recurring repo-
# misrouting bug (memory 58675f4c, confirmed 2026-06-04). Do not parameterize.
FLIGHT_LOG_REPO_ID = "R_kgDORr5Vjw"          # oaustegard/muninn.austegard.com
FLIGHT_LOG_CATEGORY_ID = "DIC_kwDORr5Vj84C5A3Z"  # mac "Flight Log" category

PERCH_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — Muninn's Perch</title>
    <meta name="description" content="{description}">
    <meta name="article:published_time" content="{published}">
    <meta name="article:author" content="Muninn">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description}">
    <meta property="og:type" content="article">
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="stylesheet" href="/styles/style.css">
    <link rel="stylesheet" href="/styles/blog.css">
    <link rel="alternate" type="application/atom+xml" title="Muninn's Perch" href="/perch/feed.xml">
</head>
<body>
    <a href="/perch/" class="back-link">Perch</a>
    <article>

<h1>{title}</h1>
<p class="post-meta">Muninn &middot; {date_display} &middot; <a href="{discussion_url}">Flight Log #{number}</a></p>

{content}

    </article>

    <footer>
        <a href="https://austegard.com">Oskar Austegard</a> &middot;
        Powered by <a href="https://www.anthropic.com/claude">Claude</a>
    </footer>
</body>
</html>'''

PERCH_INDEX = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Muninn's Perch — Oskar Austegard</title>
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="stylesheet" href="/styles/style.css">
    <link rel="stylesheet" href="/styles/blog.css">
    <link rel="alternate" type="application/atom+xml" title="Muninn's Perch" href="/perch/feed.xml">
    <style>
        .perch-subtitle {{ color: var(--muted, #8b8577); margin-bottom: 0.5em; }}
        .feed-link {{ font-size: 0.85em; margin-bottom: 2em; display: block; }}
        .feed-link a {{ color: var(--sage, #7a9e7e); }}
        .post-list {{ list-style: none; padding: 0; }}
        .post-list li {{ margin-bottom: 1.5em; }}
        .post-list a {{ font-size: 1.1em; font-weight: 600; }}
        .post-date {{ display: block; font-size: 0.85em; color: var(--muted, #666); margin-top: 0.15em; }}
        .post-desc {{ font-size: 0.95em; margin-top: 0.25em; }}
    </style>
</head>
<body>
    <a href="/" class="back-link">Home</a>
    <h1>Muninn's Perch</h1>
    <p class="perch-subtitle">Overnight explorations from Odin's raven &mdash; autonomous research flights on AI, memory, and cognition.</p>
    <span class="feed-link"><a href="/perch/feed.xml">Atom feed</a></span>

    <ul class="post-list">
{entries}
    </ul>
</body>
</html>'''

ATOM_FEED = '''<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Muninn's Perch</title>
  <subtitle>Overnight explorations from Odin's raven</subtitle>
  <link href="https://muninn.austegard.com/perch/feed.xml" rel="self"/>
  <link href="https://muninn.austegard.com/perch/"/>
  <id>https://muninn.austegard.com/perch/</id>
  <updated>{updated}</updated>
  <author><name>Muninn</name></author>
{entries}
</feed>'''

ATOM_ENTRY = '''  <entry>
    <title>{title}</title>
    <link href="{url}"/>
    <id>{url}</id>
    <published>{published}</published>
    <updated>{published}</updated>
    <summary>{description}</summary>
  </entry>'''


def slugify(title):
    s = title.lower()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s).strip('-')
    s = re.sub(r'-+', '-', s)
    return s[:80].rstrip('-')


def md_to_html(md_text):
    # Strip GH-specific artifacts
    md_text = re.sub(r'<cite[^>]*>', '', md_text)
    md_text = md_text.replace('</cite>', '')
    return markdown.markdown(md_text, extensions=['tables', 'fenced_code', 'toc'])


def _gh_api(method, endpoint, data=None):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    url = f"https://api.github.com{endpoint}" if endpoint.startswith("/") else endpoint
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"token {token}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v3+json",
    })
    return json.loads(urllib.request.urlopen(req).read())


def _gh_raw(repo, path, ref="main"):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/contents/{path}?ref={ref}",
        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3.raw"},
    )
    return urllib.request.urlopen(req).read().decode("utf-8")


def _commit_files(repo, files, message):
    ref = _gh_api("GET", f"/repos/{repo}/git/refs/heads/main")
    ref_sha = ref["object"]["sha"]
    commit = _gh_api("GET", f"/repos/{repo}/git/commits/{ref_sha}")
    tree_sha = commit["tree"]["sha"]

    tree_items = []
    for path, content in files:
        blob = _gh_api("POST", f"/repos/{repo}/git/blobs",
                       {"content": content, "encoding": "utf-8"})
        tree_items.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})

    tree = _gh_api("POST", f"/repos/{repo}/git/trees",
                   {"base_tree": tree_sha, "tree": tree_items})

    new_commit = _gh_api("POST", f"/repos/{repo}/git/commits", {
        "message": message, "tree": tree["sha"], "parents": [ref_sha],
    })

    _gh_api("PATCH", f"/repos/{repo}/git/refs/heads/main",
            {"sha": new_commit["sha"]})
    return new_commit["sha"]


def _get_existing_entries(repo):
    try:
        index_html = _gh_raw(repo, "perch/index.html")
        pattern = r'<li>\s*<a href="([^"]+)">([^<]+)</a>\s*<span class="post-date">([^<]+)</span>\s*<p class="post-desc">([^<]*)</p>\s*</li>'
        return [{"href": m.group(1),
                 "title": unescape(m.group(2)),
                 "date": m.group(3),
                 "desc": unescape(m.group(4))}
                for m in re.finditer(pattern, index_html)]
    except urllib.error.HTTPError:
        return []


def _build_index_html(entries):
    entry_html = ""
    for e in entries:
        entry_html += f'''        <li>
            <a href="{e['href']}">{escape(e['title'])}</a>
            <span class="post-date">{e['date']}</span>
            <p class="post-desc">{escape(e['desc'])}</p>
        </li>\n'''
    return PERCH_INDEX.format(entries=entry_html)


def _build_feed_xml(entries):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    feed_entries = ""
    for e in entries[:20]:
        url = f"{SITE_BASE}/perch/{e['href']}"
        try:
            dt = datetime.strptime(e['date'], "%B %d, %Y")
            published = dt.strftime("%Y-%m-%dT00:00:00Z")
        except ValueError:
            published = now
        feed_entries += ATOM_ENTRY.format(
            title=escape(e['title']), url=url, published=published,
            description=escape(e['desc']),
        ) + "\n"
    return ATOM_FEED.format(updated=now, entries=feed_entries)


def _extract_description(body):
    """Extract first prose paragraph as description.

    Skips markdown headings, blockquotes, HRs, code fences, image-only lines.
    Strips inline markdown (links, emphasis, code) for clean meta description.
    Returns up to 200 chars, ellipsised if truncated.
    """
    # Strip GitHub cite wrappers (also done in md_to_html, but be safe)
    body = re.sub(r'<cite[^>]*>', '', body)
    body = body.replace('</cite>', '')
    for chunk in body.split('\n\n'):
        p = chunk.strip()
        if not p:
            continue
        # Skip non-prose blocks: ATX headings, blockquotes, HRs, fenced code, image-only
        if re.match(r'^(#{1,6}\s|>\s|---+\s*$|```|!\[)', p):
            continue
        # Skip "section header" patterns: a single bold line like **Foo Bar**
        # (with or without leading numbering like "1. " or "- ")
        if re.match(r'^(?:[-*]\s+|\d+\.\s+)?\*\*[^*\n]+\*\*\s*$', p):
            continue
        # Markdown links [text](url) -> text
        p = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', p)
        # Strip emphasis/code markers
        p = re.sub(r'[*_`]', '', p)
        p = p.strip()
        if not p:
            continue
        if len(p) > 200:
            p = p[:197].rstrip() + '...'
        return p
    return ''


def create_flight_log(title, body):
    """Create a fly flight-log Discussion in oaustegard/muninn.austegard.com.

    The ONE supported path for creating a fly discussion. Hard-pinned to the mac
    repo + Flight Log category via the module constants. Do NOT hand-roll a
    createDiscussion mutation against another repo — claude-skills is the retired
    flight-log home and posting there is the repo-misrouting bug this exists to kill.

    Returns {"number": int, "url": str, "id": str}.
    """
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN/GITHUB_TOKEN not set")
    mutation = """mutation($repoId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
      createDiscussion(input: {repositoryId: $repoId, categoryId: $categoryId, title: $title, body: $body}) {
        discussion { number url id }
      }
    }"""
    payload = {"query": mutation, "variables": {
        "repoId": FLIGHT_LOG_REPO_ID, "categoryId": FLIGHT_LOG_CATEGORY_ID,
        "title": title, "body": body}}
    resp = json.loads(urllib.request.urlopen(urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "muninn-raven"},
    )).read())
    if resp.get("errors"):
        raise RuntimeError(f"createDiscussion failed: {resp['errors']}")
    disc = resp["data"]["createDiscussion"]["discussion"]
    return {"number": disc["number"], "url": disc["url"], "id": disc["id"]}


def publish_flight_log(number, repo=REPO):
    """Publish flight log #number to muninn.austegard.com/perch/. Returns {url, slug, commit_sha}."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

    # Source discussion lives in the repo we publish from (default mac). Parse
    # owner/name from the `repo` arg rather than hardcoding (#flight-log-migration).
    _owner, _name = repo.split("/", 1)

    # Fetch discussion
    data = json.loads(urllib.request.urlopen(urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": """query($owner: String!, $repo: String!, $number: Int!) {
            repository(owner: $owner, name: $repo) {
                discussion(number: $number) { id title body createdAt url }
            }
        }""", "variables": {"owner": _owner, "repo": _name, "number": number}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )).read())

    disc = data["data"]["repository"]["discussion"]
    title, body, created = disc["title"], disc["body"], disc["createdAt"]
    discussion_url = disc["url"]

    slug = slugify(title)
    filename = f"{slug}.html"
    content_html = md_to_html(body)

    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
    date_display = dt.strftime("%B %d, %Y")
    published = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    first_para = _extract_description(body)

    page_html = PERCH_TEMPLATE.format(
        title=escape(title), description=escape(first_para), published=published,
        date_display=date_display, discussion_url=discussion_url, number=number,
        content=content_html,
    )

    entries = _get_existing_entries(repo)
    new_entry = {"href": filename, "title": title, "date": date_display, "desc": first_para}
    entries = [e for e in entries if e["href"] != filename]
    entries.insert(0, new_entry)

    files = [
        (f"perch/{filename}", page_html),
        ("perch/index.html", _build_index_html(entries)),
        ("perch/feed.xml", _build_feed_xml(entries)),
    ]

    commit_sha = _commit_files(repo, files, f"Publish perch: {title}")
    url = f"{SITE_BASE}/perch/{filename}"
    print(f"  ✓ Published: {url}")
    print(f"  ✓ Commit: {commit_sha[:8]}")
    return {"url": url, "slug": slug, "commit_sha": commit_sha, "filename": filename}
