"""
blog_publish.py — Blog post publishing protocol (flowing-graph orchestrator).

Same public API as the prior imperative version, but `publish_and_announce`
is now a `flowing` DAG internally. The wins:

  - The deploy poll is `retry_until=`, not a hand-rolled `while time.time()` loop.
  - The feed-update gate is structural (`when=`), not an `if` in the orchestrator.
  - Bsky announce + engagement-link are detached side-effects: callers get the
    page URL the moment the deploy lands; bsky failure lands in
    `flow.detached_failures`, never bubbling up as a publish failure.
  - The 300-grapheme bsky limit is enforced as `validate=` BEFORE the post
    fires — no wasted createRecord on a too-long draft.

See issue oaustegard/claude-skills#616 for the rationale.

Public API (unchanged):

    from blog_publish import publish_and_announce, bsky_auth

    auth = bsky_auth()
    result = publish_and_announce(
        path="blog/my-post.html",
        content=html,
        bsky_text="New post — check it out",
        auth=auth,
        feed_entry={...},
    )

`result` keys:
    page_url       — the canonical URL of the published page
    commit_sha     — sha of the page commit
    feed_sha       — sha of the feed commit (None if no feed)
    deployed       — bool: did GH Pages serve the URL within the budget?
    bsky_post      — dict with uri/cid/url/rkey, or None if SKIPPED/FAILED
    update_sha     — sha of the engagement-link commit, or None
    detached_failures — list of (name, error) for any backgrounded failure

The bsky chain is detached: a failure there populates `detached_failures`
but does NOT raise. Callers that need a hard error on bsky failure should
inspect `result["detached_failures"]`.
"""

import base64
import json
import os
import re
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from bsky_card import compose_link_post, final_text_for_post
from bsky_limit import fits as _bsky_fits, BSKY_LIMIT
from flowing import task, Flow, StepState


# ── Bluesky auth ───────────────────────────────────────────────────

def bsky_auth(handle_var="MUNINN_BSKY_HANDLE", password_var="MUNINN_BSKY_APP_PASSWORD"):
    """Authenticate with Bluesky. Returns auth dict.

    Defaults to Muninn's credentials. For Oskar's account:
        bsky_auth(handle_var="BSKY_HANDLE", password_var="BSKY_APP_PASSWORD")
    """
    handle = os.environ[handle_var]
    password = os.environ[password_var]
    payload = json.dumps({
        "identifier": handle,
        "password": password,
    }).encode()
    req = urllib.request.Request(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    session = json.loads(urllib.request.urlopen(req).read())
    print(f"  ✓ Authenticated as {session['handle']}")
    return {"access_jwt": session["accessJwt"], "did": session["did"], "handle": session["handle"]}


# ── GitHub helpers ─────────────────────────────────────────────────

_MUNINN_REPO = "oaustegard/muninn.austegard.com"
_MUNINN_BASE = "https://muninn.austegard.com"

def _gh_token():
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")


def _gh_api(method, endpoint, data=None):
    token = _gh_token()
    url = f"https://api.github.com{endpoint}" if endpoint.startswith("/") else endpoint
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "User-Agent": "muninn-raven",
        "Authorization": f"token {token}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v3+json",
    })
    return json.loads(urllib.request.urlopen(req).read())


def _gh_raw(repo, path, ref="main"):
    """Get raw file content from GitHub."""
    token = _gh_token()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/contents/{path}?ref={ref}",
        headers={
            "User-Agent": "muninn-raven",
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3.raw",
        },
    )
    return urllib.request.urlopen(req).read().decode("utf-8")


def _gh_path_exists(repo, path, ref="main"):
    """True iff `path` exists in `repo` at `ref`. One GitHub API call."""
    token = _gh_token()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/contents/{path}?ref={ref}",
        method="HEAD",
        headers={
            "User-Agent": "muninn-raven",
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        resp = urllib.request.urlopen(req)
        return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


# ── Pre-commit HTML validation (issue #20) ─────────────────────────

# Maps a netloc to its GitHub Pages repo so we know when an og:image URL points
# at an asset we can verify with _gh_path_exists. External CDNs / other hosts
# are skipped — we can't check what isn't ours.
_NETLOC_TO_REPO = {
    "muninn.austegard.com": "oaustegard/muninn.austegard.com",
    "austegard.com": "oaustegard/oaustegard.github.io",
}


def validate_blog_html(content: str, repo: str, branch: str = "main") -> None:
    """Pre-commit invariants for muninn.austegard.com / austegard.com posts.

    Raises ValueError with a clear message on the first violation. Each check
    corresponds to a real past failure mode; see issue oaustegard/muninn-utilities#20
    for the post-mortem table.

    Checks (in order):
        1. <meta property="article:published_time"> present + parseable ISO timestamp
        2. Byline uses class="post-meta"
        3. <meta name="bsky:uri"> stub present
        4. If og:image is set, body contains an inline <img>
        5. If og:image points to an asset in `repo`, that asset exists
        6. All inline <img> tags have non-empty alt=""
        7. No non-structural HTML entities in <title> / og:title / og:description /
           description / article:summary content (Bluesky CardyB does not decode)

    `repo` and `branch` are used only by check 5 (the existence probe).
    """
    # 1. article:published_time — feed.xml indexing depends on this.
    m = re.search(
        r'<meta[^>]+article:published_time[^>]+content="([^"]+)"', content)
    if not m:
        raise ValueError(
            "Missing article:published_time meta tag — post will be invisible "
            "to feed.xml. See generating-lattice.html / portrait-mode-for-svgs "
            "post-mortems (memories 61758c22, e5661f26)."
        )
    ts = m.group(1)
    try:
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError(
            f"article:published_time content {ts!r} is not a parseable ISO "
            f"timestamp ({e})."
        )

    # 2. Byline class — build_blog.py date parser depends on the exact class name.
    if not re.search(r'<p[^>]+class="post-meta"', content):
        raise ValueError(
            'Byline must use class="post-meta" (not "meta" / "byline" / "author") '
            "— build_blog.py date parser depends on it."
        )

    # 3. bsky:uri stub — link_engagement UPDATES but does not INSERT.
    if not re.search(r'<meta\s+name="bsky:uri"', content):
        raise ValueError(
            'Missing <meta name="bsky:uri" content=""> stub — link_engagement '
            "updates but does not insert. Engagement widget will silently fail "
            "to wire (memory 225433fb)."
        )

    # 4 + 5. og:image consistency: inline <img>, and asset existence.
    og = re.search(r'<meta[^>]+og:image[^>]+content="([^"]+)"', content)
    if og:
        og_url = og.group(1)
        article = re.search(r'<article[^>]*>(.*?)</article>', content, re.S)
        if not article or not re.search(r'<img\b', article.group(1)):
            raise ValueError(
                "og:image is set but no <img> appears in the article body — "
                "hero will only show on Bluesky link cards, not on the page "
                "(tg-cli-for-tangled post-mortem, 2026-05-13)."
            )

        # Resolve og:image to a repo-relative path if it points at this repo's
        # site. External hosts → skip the existence check.
        from urllib.parse import urlparse
        parsed = urlparse(og_url)
        if parsed.scheme:
            if _NETLOC_TO_REPO.get(parsed.netloc) == repo:
                asset_path = parsed.path.lstrip("/")
            else:
                asset_path = None  # external CDN, can't verify in this repo
        else:
            asset_path = og_url.lstrip("/")

        if asset_path and not _gh_path_exists(repo, asset_path, branch):
            raise ValueError(
                f"og:image points to {og_url!r} but {asset_path} does not "
                f"exist in {repo} at ref {branch}."
            )

    # 6. All inline <img> tags need non-empty alt="…".
    for tag in re.finditer(r'<img\s[^>]*>', content):
        if not re.search(r'\salt="[^"]+"', tag.group(0)):
            raise ValueError(
                f"Inline <img> missing non-empty alt attribute: "
                f"{tag.group(0)[:120]}"
            )

    # 7. No non-structural HTML entities in social-card meta content.
    # Bluesky's CardyB scraper reads <title> / og:title / og:description /
    # description / article:summary verbatim and does not decode HTML entities,
    # so "&rsquo;" surfaces literally on the card. Allowed: the five entities
    # that are structurally necessary in HTML attributes / titles
    # (& < > " '). Everything else must be typed as Unicode.
    # See i-dont-have-a-watch.html post-mortem (PR #138 on
    # muninn.austegard.com, memory 03b43720, 2026-05-13).
    _ENTITY_RE = re.compile(r'&(?:[a-zA-Z][a-zA-Z0-9]*|#\d+|#x[0-9a-fA-F]+);')
    _ALLOWED_ENTITIES = {"&amp;", "&lt;", "&gt;", "&quot;", "&apos;"}
    _CARD_FIELDS = (
        (r'<title>([^<]*)</title>', "<title>"),
        (r'<meta\s+name="description"\s+content="([^"]*)"',
         '<meta name="description">'),
        (r'<meta\s+name="article:summary"\s+content="([^"]*)"',
         '<meta name="article:summary">'),
        (r'<meta\s+property="og:title"\s+content="([^"]*)"',
         '<meta property="og:title">'),
        (r'<meta\s+property="og:description"\s+content="([^"]*)"',
         '<meta property="og:description">'),
    )
    for pattern, label in _CARD_FIELDS:
        m = re.search(pattern, content)
        if not m:
            continue
        bad = sorted({
            e for e in _ENTITY_RE.findall(m.group(1))
            if e not in _ALLOWED_ENTITIES
        })
        if bad:
            raise ValueError(
                f"HTML entity reference(s) {bad} in {label} content — "
                f"Bluesky's CardyB scraper does not decode entities in meta "
                f"content, so the card will render them literally (e.g. "
                f"\"I don&rsquo;t\" instead of \"I don\u2019t\"). Use Unicode "
                f"characters directly in card-surfaced fields "
                f"(\u2019 \u2018 \u201c \u201d \u2014 \u2026). "
                f"See i-dont-have-a-watch.html post-mortem, 2026-05-13."
            )


# ── Template-filler (issue #67) ────────────────────────────────────

# Per-session cache of fetched templates, keyed by (repo, ref). The template
# changes rarely; fetching it once per session is enough.
_TEMPLATE_CACHE: dict = {}

# The five HTML entities that are structurally legal in attribute / title
# content. Everything else must be a literal Unicode character, because
# check 7 of validate_blog_html rejects entities in card-surfaced fields and
# Bluesky's CardyB scraper renders them literally. We don't decode here — we
# refuse, so the caller fixes the source text rather than shipping a broken
# card. Mirrors _ALLOWED_ENTITIES in validate_blog_html.
_CARD_SAFE_ENTITIES = {"&amp;", "&lt;", "&gt;", "&quot;", "&apos;"}
_CARD_ENTITY_RE = re.compile(r'&(?:[a-zA-Z][a-zA-Z0-9]*|#\d+|#x[0-9a-fA-F]+);')


def _attr_escape(s: str) -> str:
    """Escape a string for use inside a double-quoted HTML attribute / title.

    Only the structural five (& < > " ') are escaped, and only where needed.
    Unicode is left intact — check 7 of validate_blog_html WANTS literal
    Unicode (curly quotes, em-dashes) in card fields, not entities.
    """
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )


def _assert_card_safe(field_name: str, value: str) -> None:
    """Raise if `value` carries non-structural HTML entities.

    Pre-flights check 7 of validate_blog_html for the card-surfaced fields
    (title, description, summary) so the failure names the offending argument
    instead of surfacing later as an opaque validator raise on assembled HTML.
    """
    bad = sorted({
        e for e in _CARD_ENTITY_RE.findall(value)
        if e not in _CARD_SAFE_ENTITIES
    })
    if bad:
        raise ValueError(
            f"{field_name} contains HTML entity reference(s) {bad}. Bluesky's "
            f"CardyB scraper does not decode entities in card fields — they "
            f"render literally. Pass literal Unicode instead "
            f"(\u2019 \u2018 \u201c \u201d \u2014 \u2026). "
            f"See validate_blog_html check 7."
        )


def new_post(title, summary, body_html, *, author="Muninn", published=None,
             repo="oaustegard/muninn.austegard.com", og_image=None,
             description=None, ref="main") -> str:
    """Build a blog-post HTML document from `blog/_template.html`, filled.

    The point (issue #67): collapse "follow the publishing procedure" into
    "call one function," so freehanding the HTML — or scraping a live post for
    its structure — stops being the path of least resistance. The returned
    string passes `validate_blog_html(html, repo)` by construction.

    Args:
        title:       Post title. Used for <title>, <h1>, og:title.
        summary:     Short summary. Used for <meta name="description">,
                     og:description, and (unless `description` differs) the
                     index text. Surfaces on the Bluesky card — keep it clean
                     Unicode, no HTML entities.
        body_html:   The article body as an HTML fragment (already-rendered
                     <p>/<h2>/<img>… markup). Inserted verbatim inside
                     <article>. If `og_image` is set, this MUST contain at
                     least one <img> with a non-empty alt="" (validator
                     check 4 + 6) — the hero has to render on-page, not only
                     on the card.
        author:      Byline name. Defaults to "Muninn".
        published:   ISO-8601 timestamp for article:published_time. Defaults
                     to now (UTC). feed.xml indexing depends on this tag.
        repo:        Site repo the post will live in. Selects the template
                     source and is the repo validate_blog_html probes for the
                     og:image asset. Defaults to muninn.austegard.com.
        og_image:    Optional hero image URL/path for the og:image meta. When
                     set, `body_html` must include a matching inline <img>,
                     and the asset must already be committed to `repo`
                     (commit it via publish_page BEFORE publishing the post —
                     validate_blog_html check 5 probes for it at `ref`).
        description: Optional <meta name="description"> override when you want
                     it to differ from `summary`. Defaults to `summary`.
        ref:         Git ref to fetch the template from. Defaults to "main".

    Returns:
        A complete HTML document string, conformant to validate_blog_html.

    Raises:
        ValueError: if the template fetch fails (no silent freehand fallback),
            or if a card field carries non-structural HTML entities.

    Then the documented flow is:
        html = new_post(title, summary, body_html, og_image=...)
        result = publish_and_announce(path, html, bsky_text, auth, feed_entry=...)
    """
    # 1. Fetch the template — hard requirement, no fallback. A freehand
    #    fallback here would defeat the entire purpose of the issue.
    cache_key = (repo, ref)
    if cache_key not in _TEMPLATE_CACHE:
        try:
            _TEMPLATE_CACHE[cache_key] = _gh_raw(repo, "blog/_template.html", ref)
        except Exception as e:
            raise ValueError(
                f"Could not fetch blog/_template.html from {repo}@{ref}: {e}. "
                f"new_post refuses to freehand the HTML — fix the fetch "
                f"(token? repo? ref?) and retry."
            ) from e
    html = _TEMPLATE_CACHE[cache_key]

    if published is None:
        published = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        # Validate early so the caller sees a clear error, not a later
        # validate_blog_html raise on assembled HTML.
        try:
            datetime.fromisoformat(str(published).replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(
                f"published={published!r} is not a parseable ISO timestamp "
                f"({e})."
            ) from e

    if description is None:
        description = summary

    # Card-surfaced fields must be entity-free (validator check 7). Refuse
    # loudly now, naming the argument, instead of letting the assembled-HTML
    # validator raise on an anonymous match later.
    _assert_card_safe("title", title)
    _assert_card_safe("summary", summary)
    _assert_card_safe("description", description)

    title_a = _attr_escape(title)
    desc_a = _attr_escape(description)
    summary_a = _attr_escape(summary)

    # Human-readable byline date in the site's "Month Day, Year" style.
    _dt = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
    byline_date = f"{_dt.strftime('%B')} {_dt.day}, {_dt.year}"

    # 2. Fill placeholders by targeted replacement of the template's known
    #    marker strings. Replacing exact markers (rather than regex-rebuilding
    #    the document) keeps new_post coupled to the template's structure: if
    #    the template changes a marker, the unfilled placeholder shows up in
    #    output and the validator or a human catches it, instead of new_post
    #    silently emitting its own divergent HTML.
    replacements = [
        # <title> + og:title + <h1>
        ("<title>Post Title Here</title>", f"<title>{title_a}</title>"),
        ('<meta property="og:title" content="Post Title Here">',
         f'<meta property="og:title" content="{title_a}">'),
        ("<h1>Post Title Here</h1>", f"<h1>{title}</h1>"),
        # description + og:description
        ('<meta name="description" content="A short summary for search '
         'engines and the blog index.">',
         f'<meta name="description" content="{desc_a}">'),
        ('<meta property="og:description" content="A short summary for search '
         'engines and the blog index.">',
         f'<meta property="og:description" content="{desc_a}">'),
        # article:summary (index text)
        ('<meta name="article:summary" content="Summary shown on the blog '
         'index page.">',
         f'<meta name="article:summary" content="{summary_a}">'),
        # published_time
        ('<meta name="article:published_time" content="2026-01-01T00:00:00Z">',
         f'<meta name="article:published_time" content="{published}">'),
        # author meta
        ('<meta name="article:author" content="Oskar Austegard">',
         f'<meta name="article:author" content="{_attr_escape(author)}">'),
        # byline — class="post-meta" is preserved (validator check 2)
        ('<p class="post-meta">Written by Author &middot; Month Day, Year</p>',
         f'<p class="post-meta">Written by {author} \u00b7 {byline_date}</p>'),
        # body — replace the placeholder content block
        ("<!-- Post content goes here -->\n<p>First paragraph...</p>",
         body_html),
        # bsky:uri — collapse the example AT-URI to an empty stub so
        # link_engagement can fill it post-announce (validator check 3 only
        # needs the tag present; the inline auto-wire script skips on '...').
        ('<meta name="bsky:uri" content="at://did:plc:.../app.bsky.feed.post/...">',
         '<meta name="bsky:uri" content="">'),
    ]
    for old, new in replacements:
        html = html.replace(old, new)

    # 3. og:image: the template ships a commented-out-by-example tag with a
    #    placeholder path. Set it to the real URL, or strip the line if no
    #    hero — leaving the placeholder path would fail validator check 5
    #    (asset doesn't exist).
    og_line_re = re.compile(
        r'[ \t]*<meta property="og:image" content="[^"]*">\n?')
    if og_image:
        html = og_line_re.sub(
            f'    <meta property="og:image" content="{_attr_escape(og_image)}">\n',
            html, count=1)
    else:
        html = og_line_re.sub("", html, count=1)

    # 4. Construct-time guarantee: the returned HTML passes the validator.
    #    This is the contract ("returns HTML that passes validate_blog_html by
    #    construction") enforced, not merely asserted in the docstring.
    validate_blog_html(html, repo, ref)
    return html


def publish_page(repo, path, content, message=None):
    """Commit a single file to GitHub Pages repo. Returns commit SHA.

    `content` may be `str` (committed as UTF-8 text) or `bytes`
    (base64-encoded for the blobs API so binary files round-trip without
    corruption). See issue oaustegard/muninn-utilities#31 — passing the
    base64 text of a PNG with utf-8 encoding stored the base64 string
    as the file body, bloating it ~4/3 and breaking image rendering.
    """
    if not message:
        message = f"Publish {path}"

    if isinstance(content, bytes):
        blob_payload = {
            "content": base64.b64encode(content).decode("ascii"),
            "encoding": "base64",
        }
    else:
        blob_payload = {"content": content, "encoding": "utf-8"}

    ref = _gh_api("GET", f"/repos/{repo}/git/refs/heads/main")
    ref_sha = ref["object"]["sha"]
    commit = _gh_api("GET", f"/repos/{repo}/git/commits/{ref_sha}")
    tree_sha = commit["tree"]["sha"]

    blob = _gh_api("POST", f"/repos/{repo}/git/blobs", blob_payload)

    tree = _gh_api("POST", f"/repos/{repo}/git/trees", {
        "base_tree": tree_sha,
        "tree": [{"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]}],
    })

    new_commit = _gh_api("POST", f"/repos/{repo}/git/commits", {
        "message": message, "tree": tree["sha"], "parents": [ref_sha],
    })

    _gh_api("PATCH", f"/repos/{repo}/git/refs/heads/main",
            {"sha": new_commit["sha"]})

    return new_commit["sha"]


# ── Atom feed maintenance ──────────────────────────────────────────

ATOM_NS = "http://www.w3.org/2005/Atom"

def update_feed(repo, feed_path, page_url, entry, message=None):
    """Add an entry to the Atom feed and update the <updated> timestamp.

    entry dict keys:
        title (required): Post title
        summary (required): Brief description
        published (optional): ISO datetime, defaults to now
        updated (optional): ISO datetime, defaults to published

    Returns commit SHA.
    """
    ET.register_namespace("", ATOM_NS)

    current_xml = _gh_raw(repo, feed_path)
    root = ET.fromstring(current_xml)

    ns = {"atom": ATOM_NS}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    published = entry.get("published", now)
    updated = entry.get("updated", published)

    feed_updated = root.find("atom:updated", ns)
    if feed_updated is not None:
        feed_updated.text = now

    new_entry = ET.SubElement(root, f"{{{ATOM_NS}}}entry")
    ET.SubElement(new_entry, f"{{{ATOM_NS}}}title").text = entry["title"]

    link = ET.SubElement(new_entry, f"{{{ATOM_NS}}}link")
    link.set("href", page_url)
    link.set("rel", "alternate")
    link.set("type", "text/html")

    ET.SubElement(new_entry, f"{{{ATOM_NS}}}id").text = page_url
    ET.SubElement(new_entry, f"{{{ATOM_NS}}}published").text = published
    ET.SubElement(new_entry, f"{{{ATOM_NS}}}updated").text = updated
    ET.SubElement(new_entry, f"{{{ATOM_NS}}}summary").text = entry["summary"]

    output = _pretty_feed(root, ns)

    if not message:
        message = f"Add feed entry: {entry['title']}"

    sha = publish_page(repo, feed_path, output, message=message)
    print(f"  ✓ Feed updated with: {entry['title']}")
    return sha


def _pretty_feed(root, ns):
    """Serialize Atom feed with readable formatting."""
    lines = ['<?xml version="1.0" encoding="utf-8"?>']
    lines.append('<feed xmlns="http://www.w3.org/2005/Atom">')

    for child in root:
        tag = child.tag.replace(f"{{{ATOM_NS}}}", "")
        if tag == "entry":
            continue
        if len(child) == 0 and child.text:
            attribs = "".join(f' {k}="{v}"' for k, v in child.attrib.items())
            lines.append(f"  <{tag}{attribs}>{child.text}</{tag}>")
        elif len(child) == 0:
            attribs = "".join(f' {k}="{v}"' for k, v in child.attrib.items())
            lines.append(f"  <{tag}{attribs}/>")
        else:
            attribs = "".join(f' {k}="{v}"' for k, v in child.attrib.items())
            inner = ""
            for sub in child:
                stag = sub.tag.replace(f"{{{ATOM_NS}}}", "")
                inner += f"<{stag}>{sub.text or ''}</{stag}>"
            lines.append(f"  <{tag}{attribs}>{inner}</{tag}>")

    for entry in root.findall("atom:entry", ns):
        lines.append("")
        lines.append("  <entry>")
        for child in entry:
            tag = child.tag.replace(f"{{{ATOM_NS}}}", "")
            attribs = "".join(f' {k}="{v}"' for k, v in child.attrib.items())
            if child.text:
                lines.append(f"    <{tag}{attribs}>{child.text}</{tag}>")
            else:
                lines.append(f"    <{tag}{attribs}/>")
        lines.append("  </entry>")

    lines.append("")
    lines.append("</feed>")
    lines.append("")
    return "\n".join(lines)


# ── Deploy probing ─────────────────────────────────────────────────

def _probe_url(url: str) -> bool:
    """One HEAD probe. True iff status 200."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        resp = urllib.request.urlopen(req)
        return resp.status == 200
    except (urllib.error.HTTPError, urllib.error.URLError):
        return False


def wait_for_deploy(url, timeout=120, poll_interval=10):
    """Poll a URL until it returns 200. Returns True on success.

    Retained for backward compat / step-by-step usage. The flowing
    orchestrator in `publish_and_announce` uses the `retry_until=` primitive
    instead, which is the same behavior expressed structurally.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _probe_url(url):
            print(f"  ✓ {url} is live")
            return True
        remaining = int(deadline - time.time())
        print(f"  … waiting for deploy ({remaining}s remaining)")
        time.sleep(poll_interval)
    print(f"  ✗ Timeout waiting for {url}")
    return False


# ── Engagement linking ─────────────────────────────────────────────

_SITE_TO_REPO = {
    "austegard.com": "oaustegard/oaustegard.github.io",
    "muninn.austegard.com": "oaustegard/muninn.austegard.com",
}


def _bsky_url_to_at_uri(bsky_url):
    """Convert https://bsky.app/profile/HANDLE/post/RKEY → at://DID/app.bsky.feed.post/RKEY."""
    if bsky_url.startswith("at://"):
        return bsky_url
    m = re.match(r"https?://bsky\.app/profile/([^/]+)/post/([^/]+)", bsky_url)
    if not m:
        raise ValueError(f"Not a bsky.app post URL: {bsky_url}")
    handle, rkey = m.group(1), m.group(2)
    resp = urllib.request.urlopen(
        f"https://bsky.social/xrpc/com.atproto.identity.resolveHandle?handle={handle}"
    )
    did = json.loads(resp.read())["did"]
    return f"at://{did}/app.bsky.feed.post/{rkey}"


def link_engagement(repo, path, bsky_uri):
    """Update a page's bsky:uri meta tag and noscript link for the engagement widget.

    bsky_uri: AT URI or bsky.app URL (auto-resolved to AT URI for meta tag).
    Returns commit SHA or None if nothing to update.
    """
    at_uri = _bsky_url_to_at_uri(bsky_uri)
    m = re.match(r"at://([^/]+)/app\.bsky\.feed\.post/(.+)", at_uri)
    bsky_app_url = f"https://bsky.app/profile/{m.group(1)}/post/{m.group(2)}" if m else bsky_uri

    current = _gh_raw(repo, path)
    updated = current

    updated = re.sub(
        r'(<meta\s+name="bsky:uri"\s+content=")[^"]*(")',
        rf'\g<1>{at_uri}\2',
        updated, count=1,
    )

    updated = re.sub(
        r'(<a\s+href=")https://bsky\.app/profile/[^"]*(">\s*Discuss on Bluesky)',
        rf'\g<1>{bsky_app_url}\2',
        updated, count=1,
    )

    updated = re.sub(
        r'data-bsky-uri="[^"]*"',
        f'data-bsky-uri="{at_uri}"',
        updated, count=1,
    )

    if updated == current:
        print("  ⚠ No bsky:uri meta tag or engagement attributes found")
        return None

    sha = publish_page(repo, path, updated,
                       message=f"Link Bluesky engagement for {path}")
    print(f"  ✓ Updated {path} with Bluesky URI")
    return sha


def link_bsky(page_url, bsky_url):
    """Link a blog post to its Bluesky discussion post.

    Infers repo from domain. Returns commit SHA.
    """
    from urllib.parse import urlparse
    parsed = urlparse(page_url)
    domain = parsed.netloc
    repo = _SITE_TO_REPO.get(domain)
    if not repo:
        raise ValueError(f"Unknown domain {domain}. Known: {list(_SITE_TO_REPO.keys())}")
    path = parsed.path.lstrip("/")
    return link_engagement(repo, path, bsky_url)


# ── Full protocol (flowing graph) ──────────────────────────────────

# Default poll cadence for the GH Pages deploy. Retained at 10s × 12 to match
# the prior wait_for_deploy(timeout=120, poll_interval=10) budget.
_DEPLOY_POLL_MS = 10_000
_DEPLOY_RETRIES = 12


def publish_and_announce(path, content, bsky_text, auth,
                         repo=_MUNINN_REPO,
                         site_base=_MUNINN_BASE,
                         feed_path="feed.xml",
                         feed_entry=None,
                         commit_message=None,
                         skip_deploy_wait=False,
                         validate_html=True,
                         reindex=None):
    """Publish page → wait for deploy → update feed; bsky + reindex run detached.

    Internal shape (flowing graph):

        publish_page_node ──▶ wait_for_deploy_node ──▶ update_feed_node  [terminal]
                                       │
                                       ├──▶ announce_bsky [detached]
                                       │          │
                                       │          └──▶ link_engagement_node [detached]
                                       └──▶ reindex_node [detached]  (only if reindex=)

    The detached legs are auto-discovered (v1.2 flowing) — each depends on
    wait_for_deploy_node, reachable from the terminal, so the runner picks them
    up without an explicit terminal of their own. Failures there land in
    `flow.detached_failures` and the function still returns the page URL.

    See issue oaustegard/claude-skills#616.

    `validate_html=True` runs `validate_blog_html(content, repo)` BEFORE the
    flow builds — raises ValueError on the first failed invariant so nothing
    commits. Set False to skip (e.g. for non-blog pages with different shape).
    See issue oaustegard/muninn-utilities#20.

    The bsky-grapheme budget is also checked pre-commit (#24): if
    `bsky_text` is supplied, `final_text_for_post(bsky_text, url)` must fit
    BSKY_LIMIT before any commit lands. The detached belt-and-suspenders
    gate inside the flow stays, but the structural fix is to fail before
    publish_page commits anything.

    `reindex` is an optional zero-arg callable that refreshes the site's search
    index after the page is committed. For muninn.austegard.com the search
    index is a derived artifact in Cloudflare KV; publishing a post must refresh
    it or the post is unfindable. There is no CI for this — the publisher (this
    session) owns the reindex, so it is wired in here as a step of the publish
    flow rather than a separate workflow. It runs detached: a reindex failure
    lands in `detached_failures`, never blocking the page/bsky result, and its
    return value surfaces as `result["reindexed"]`. Pass None to skip (non-blog
    pages, or sites without a search index).
    """
    if validate_html:
        validate_blog_html(content, repo)

    url = f"{site_base}/{path}"

    # Pre-commit bsky budget gate (#24). Run BEFORE the flow builds so a
    # budget violation blocks the page commit, not just the announce leg.
    # Mirrors must_be_under_bsky_limit (below) — measures the post-parse
    # record.text that AT Proto actually counts (markdown stripped, URL
    # appended if not already linked). Same pre-flight raise shape as
    # validate_blog_html: no commits land if this fires.
    if bsky_text is not None:
        composed = final_text_for_post(bsky_text, url)
        if not _bsky_fits(composed):
            raise ValueError(
                f"bsky_text (after markdown strip + URL append) exceeds "
                f"{BSKY_LIMIT} graphemes — would be rejected by AT Proto. "
                "Trim bsky_text before calling, or use bsky_limit.truncate()."
            )

    @task(name="publish_page_node")
    def publish_page_node():
        sha = publish_page(repo, path, content, commit_message)
        print(f"  ✓ Page committed: {sha[:10]}")
        return {"commit_sha": sha, "url": url}

    @task(
        name="wait_for_deploy_node",
        depends_on=[publish_page_node],
        retry=_DEPLOY_RETRIES,
        retry_backoff_base_ms=_DEPLOY_POLL_MS,
        retry_max_backoff_ms=_DEPLOY_POLL_MS,
        retry_until=lambda r: r["deployed"],
    )
    def wait_for_deploy_node(publish_page_node):
        if skip_deploy_wait:
            return {"deployed": True, "skipped": True, "url": url}
        live = _probe_url(url)
        if live:
            print(f"  ✓ {url} is live")
        return {"deployed": live, "url": url}

    @task(
        name="update_feed_node",
        depends_on=[wait_for_deploy_node],
        when=lambda **_: feed_path is not None and feed_entry is not None,
    )
    def update_feed_node(wait_for_deploy_node):
        sha = update_feed(repo, feed_path, url, feed_entry)
        return {"feed_sha": sha}

    def must_be_under_bsky_limit(**deps):
        # Measure the post-parse record.text (markdown stripped, target URL
        # appended only if not already facet-linked) — what AT Proto will
        # actually count. Raw bsky_text under-rejects when the URL append
        # adds 80+ graphemes; over-rejects when markdown shrinks the visible
        # text. Issue oaustegard/muninn-utilities#11.
        final = final_text_for_post(bsky_text, url)
        if not _bsky_fits(final):
            raise ValueError(
                f"bsky_text (after markdown strip + URL append) exceeds "
                f"{BSKY_LIMIT} graphemes — would be rejected by AT Proto. "
                "Trim before calling, or use bsky_limit.truncate()."
            )

    @task(
        name="announce_bsky",
        depends_on=[wait_for_deploy_node],
        validate=must_be_under_bsky_limit,
        detached=True,
    )
    def announce_bsky(wait_for_deploy_node):
        # compose_link_post runs its own internal flow (compose + post)
        # and returns {record, post, og_tags, thumb_blob, facets, ...}.
        result = compose_link_post(bsky_text, url, auth)
        return result["post"]

    @task(
        name="link_engagement_node",
        depends_on=[announce_bsky],
        detached=True,
    )
    def link_engagement_node(announce_bsky):
        sha = link_engagement(repo, path, announce_bsky["url"])
        return {"update_sha": sha}

    # Reindex leg — refresh the search index after the page commits. Detached
    # and conditional: only built when a reindex callable is supplied, so the
    # node never appears (and never fails) for callers that don't have a
    # search index. Depends on wait_for_deploy_node so it runs after the page
    # is committed, in parallel with the bsky announce.
    reindex_node = None
    if reindex is not None:
        @task(
            name="reindex_node",
            depends_on=[wait_for_deploy_node],
            detached=True,
        )
        def reindex_node(wait_for_deploy_node):
            out = reindex()
            print("  ✓ Search index reindexed")
            return {"reindex": out}

    flow = Flow(update_feed_node)
    flow.run()

    def _val(td, key=None, default=None):
        r = flow.results.get(td.name)
        if r is None or r.state != StepState.SUCCEEDED:
            return default
        return r.value if key is None else r.value.get(key, default)

    bsky_post = _val(announce_bsky)
    detached_failures = [(r.name, str(r.error)) for r in flow.detached_failures]

    print(f"\n✓ Done!")
    print(f"  Page: {url}")
    if bsky_post:
        print(f"  Post: {bsky_post['url']}")
    if detached_failures:
        print(f"  Detached failures: {detached_failures}")

    return {
        "page_url": url,
        "commit_sha": _val(publish_page_node, "commit_sha"),
        "deployed": bool(_val(wait_for_deploy_node, "deployed", default=False)),
        "feed_sha": _val(update_feed_node, "feed_sha"),
        "bsky_post": bsky_post,
        "update_sha": _val(link_engagement_node, "update_sha"),
        "reindexed": _val(reindex_node, "reindex") if reindex_node is not None else None,
        "detached_failures": detached_failures,
    }
