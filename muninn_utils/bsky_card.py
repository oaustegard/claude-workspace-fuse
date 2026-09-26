"""
bsky_card.py — Bluesky link card composition (flowing-graph orchestrator).

Internal shape (issue oaustegard/claude-skills#617):

    fetch_og ──▶ upload_blob_node ──┐
        │                            │
        └──▶ embed_node ◀────────────┘
                  │
    facets_node ──┼──▶ record_node ──▶ post_node  [terminal]

Wins over imperative:

  - `fetch_og` and `facets_node` parallelize (one network, one local).
  - `validate=must_have_valid_record_inputs` runs on `record_node` and
    rejects malformed embed (no uri) BEFORE any post fires — catches the
    "post a card with no target" trap structurally.
  - `upload_blob_node` failure cleanly SKIPS embed, record, and post —
    no half-baked post on the wire.
  - max_workers=3 on the Flow → the parallel legs run concurrently.

Public API: `compose_link_post(text, url, auth, og_tags=None)` runs the
full graph — compose AND post — and returns:

    {record, post, og_tags, thumb_blob, facets, detached_failures}

Note: this is an internal Muninn utility, so the prior split of
"compose_link_post returns a record / create_post submits it" was
collapsed into a single flow. Lower-level helpers (fetch_og_tags,
upload_blob, compute_facets, build_external_embed, create_post) remain
exposed for callers that want to drive their own pipeline.
"""

import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from urllib.parse import urlparse

from flowing import task, Flow, StepState


# ── OG Tag Extraction ──────────────────────────────────────────────

def fetch_og_tags(url):
    """Fetch a page and extract Open Graph meta tags.

    Returns dict with keys: url, title, description, image.
    Falls back to <title> and meta description if OG tags are absent.
    """
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (bsky-card bot)"
    })
    html = urllib.request.urlopen(req).read().decode("utf-8", errors="replace")

    tags = {"url": url}
    for prop in ["title", "description", "image"]:
        m = _match_og(html, prop)
        if m:
            tags[prop] = m

    if "title" not in tags:
        m = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
        if m:
            tags["title"] = m.group(1).strip()

    if "description" not in tags:
        m = re.search(
            r'<meta\s+name="description"\s+content="([^"]+)"',
            html, re.IGNORECASE
        )
        if m:
            tags["description"] = m.group(1)

    if tags.get("image", "").startswith("/"):
        parsed = urlparse(url)
        tags["image"] = f"{parsed.scheme}://{parsed.netloc}{tags['image']}"

    return tags


def _match_og(html, prop):
    """Try multiple patterns to extract an og: meta tag value."""
    patterns = [
        rf'<meta\s+(?:property|name)="og:{prop}"\s+content="([^"]+)"',
        rf"<meta\s+(?:property|name)='og:{prop}'\s+content='([^']+)'",
        rf'<meta\s+content="([^"]+)"\s+(?:property|name)="og:{prop}"',
        rf"<meta\s+content='([^']+)'\s+(?:property|name)='og:{prop}'",
    ]
    for pattern in patterns:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


# ── Blob Upload ────────────────────────────────────────────────────

def upload_blob(image_url, auth):
    """Download an image from a URL and upload it as a Bluesky blob.

    Returns blob dict (with $type, ref, mimeType, size) suitable for
    use as embed.external.thumb.
    """
    req = urllib.request.Request(image_url, headers={
        "User-Agent": "Mozilla/5.0 (bsky-card bot)"
    })
    resp = urllib.request.urlopen(req)
    image_data = resp.read()
    content_type = resp.headers.get("Content-Type", "image/png")

    upload_req = urllib.request.Request(
        "https://bsky.social/xrpc/com.atproto.repo.uploadBlob",
        data=image_data, method="POST",
        headers={
            "Authorization": f"Bearer {auth['access_jwt']}",
            "Content-Type": content_type
        }
    )
    result = json.loads(urllib.request.urlopen(upload_req).read())
    return result["blob"]


# ── Facet Computation ──────────────────────────────────────────────

def compute_facets(text):
    """Find URLs and #hashtags in text and create ATProto facets.

    Returns list of facet dicts with correct UTF-8 byte offsets.
    """
    facets = []

    for match in re.finditer(r'https?://\S+', text):
        url_str = match.group(0)
        while url_str and url_str[-1] in ".,;:!?)\"'":
            url_str = url_str[:-1]
        byte_start, byte_end = _byte_offsets(text, match.start(), url_str)
        facets.append({
            "index": {"byteStart": byte_start, "byteEnd": byte_end},
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url_str}]
        })

    for match in re.finditer(r'(?<!\w)#(\w+)', text):
        tag = match.group(1)
        full = match.group(0)
        byte_start, byte_end = _byte_offsets(text, match.start(), full)
        facets.append({
            "index": {"byteStart": byte_start, "byteEnd": byte_end},
            "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": tag}]
        })

    return facets


def _byte_offsets(text, char_start, matched_text):
    """Convert character position to UTF-8 byte offsets."""
    prefix_bytes = text[:char_start].encode("utf-8")
    matched_bytes = matched_text.encode("utf-8")
    return len(prefix_bytes), len(prefix_bytes) + len(matched_bytes)


# ── Markdown Link Parsing ──────────────────────────────────────────

_MARKDOWN_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')


def parse_markdown_links(text):
    """Strip `[displayed](url)` markdown links and emit facet#link entries.

    Returns `(stripped_text, facets)`. The stripped text has each markdown
    span replaced by its displayed-text only; the URL lives in
    `features[].uri` of the corresponding facet and costs zero graphemes.

    Byte offsets in `facets` reference the *stripped* text, so they can be
    concatenated with `compute_facets(stripped_text)` (and any optional
    URL append) without re-shifting.
    """
    facets = []
    out_parts = []
    pos = 0
    byte_offset = 0
    for m in _MARKDOWN_LINK_RE.finditer(text):
        before = text[pos:m.start()]
        out_parts.append(before)
        byte_offset += len(before.encode("utf-8"))

        link_text = m.group(1)
        link_url = m.group(2)
        link_bytes = link_text.encode("utf-8")
        facets.append({
            "index": {
                "byteStart": byte_offset,
                "byteEnd": byte_offset + len(link_bytes),
            },
            "features": [{
                "$type": "app.bsky.richtext.facet#link",
                "uri": link_url,
            }],
        })
        out_parts.append(link_text)
        byte_offset += len(link_bytes)
        pos = m.end()

    out_parts.append(text[pos:])
    return "".join(out_parts), facets


def _markdown_targets(facets):
    """Set of URIs already covered by markdown-derived facet#link entries."""
    return {
        feat["uri"]
        for f in facets
        for feat in f.get("features", [])
        if feat.get("$type") == "app.bsky.richtext.facet#link" and "uri" in feat
    }


def final_text_for_post(text, url):
    """Compute what `record.text` will be after `compose_link_post` shaping.

    Mirrors the text logic in `_build_compose_graph`:
      1. Strip `[displayed](url)` markdown into displayed-only text.
      2. If the target `url` isn't already covered — either as a
         markdown-link target or as a literal substring — append it on
         a new line (backwards-compatible fallback).

    Callers can use this to budget-check graphemes before invoking the
    post, replacing a raw `bsky_text` length check that would either
    over-reject (markdown shrinks the visible text) or under-reject
    (the URL append used to add 89+ graphemes).
    """
    stripped, md_facets = parse_markdown_links(text)
    if url not in _markdown_targets(md_facets) and url not in stripped:
        stripped = f"{stripped}\n{url}"
    return stripped


# ── Embed Construction ─────────────────────────────────────────────

def build_external_embed(og_tags, thumb_blob=None):
    """Build an app.bsky.embed.external embed dict from OG tags."""
    external = {
        "uri": og_tags["url"],
        "title": og_tags.get("title", ""),
        "description": og_tags.get("description", ""),
    }
    if thumb_blob:
        external["thumb"] = thumb_blob

    return {
        "$type": "app.bsky.embed.external",
        "external": external
    }


# ── Edge contracts ─────────────────────────────────────────────────

def _must_have_valid_record_inputs(**deps):
    """Edge contract for record_node: validate embed and facets shape.

    Runs against gathered dep values (embed_node, facets_node) BEFORE the
    record body fires. Catches malformed embed (no uri) or non-list facets
    so the post downstream can't fire on a broken card.
    """
    embed = deps.get("embed_node")
    if not isinstance(embed, dict):
        raise ValueError("embed_node missing or not a dict")
    external = embed.get("external") or {}
    if not external.get("uri"):
        raise ValueError("record.embed.external.uri is missing — link card has no target")

    facets = deps.get("facets_node")
    if not isinstance(facets, list):
        raise ValueError("facets_node not a list")


# ── High-Level Composition (flowing graph) ─────────────────────────

def _build_compose_graph(text, url, auth, og_tags=None, langs=None):
    """Construct the compose-pipeline tasks; return (record_node, fetch_og).

    Tasks are closure-bound to (text, url, auth, og_tags, langs). The caller
    decides which terminal to drive — record_node alone (compose only)
    or post_node downstream (compose + post).

    `langs`, when supplied, is a list of BCP-47 language tags written to the
    record's `langs` field (app.bsky.feed.post). None omits the field.
    """
    # Strip `[displayed](url)` markdown so URLs in the source text move
    # into facets (zero graphemes) instead of being visible in record.text.
    text, markdown_facets = parse_markdown_links(text)

    # If the target url is already facet-linked via markdown — or already
    # appears literally in the stripped text — skip the URL append. The
    # embed card still points at it; visible text doesn't need to.
    if url not in _markdown_targets(markdown_facets) and url not in text:
        text = f"{text}\n{url}"

    pre_supplied = og_tags

    @task(name="fetch_og")
    def fetch_og():
        if pre_supplied is not None:
            return pre_supplied
        return fetch_og_tags(url)

    @task(name="upload_blob_node", depends_on=[fetch_og])
    def upload_blob_node(fetch_og):
        img = fetch_og.get("image")
        if not img:
            # No image at all is a clean success with a None payload —
            # embed_node proceeds and builds a thumb-less card.
            return None
        # Genuine upload failure raises → embed/post SKIP. (#617 win 3.)
        return upload_blob(img, auth)

    @task(name="facets_node")
    def facets_node():
        return markdown_facets + compute_facets(text)

    @task(name="embed_node", depends_on=[upload_blob_node, fetch_og])
    def embed_node(upload_blob_node, fetch_og):
        return build_external_embed(fetch_og, thumb_blob=upload_blob_node)

    @task(
        name="record_node",
        depends_on=[embed_node, facets_node],
        validate=_must_have_valid_record_inputs,
    )
    def record_node(embed_node, facets_node):
        record = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "facets": facets_node,
            "embed": embed_node,
        }
        if langs:
            record["langs"] = langs
        return record

    return {
        "fetch_og": fetch_og,
        "upload_blob_node": upload_blob_node,
        "facets_node": facets_node,
        "embed_node": embed_node,
        "record_node": record_node,
        "_text": text,  # post-URL-append, for callers that need it
    }


def compose_link_post(text, url, auth, og_tags=None, langs=None):
    """Compose a Bluesky link-card post AND submit it. Single flowing graph.

    Runs the full pipeline:
      fetch_og + facets_node (parallel) → upload_blob_node → embed_node
        → record_node → post_node

    `langs`, when supplied, is a list of BCP-47 tags (e.g. ["en"]) recorded
    in the post's `langs` field; None omits it.

    Returns a dict with:
        record            — the assembled app.bsky.feed.post record
        post              — the create_post response (uri/cid/url/rkey)
        og_tags           — the OG tags used
        thumb_blob        — the uploaded blob, or None if no image
        facets            — the AT Proto facets list
        detached_failures — always [] (included for API symmetry with
                            publish_and_announce)

    Raises on any hard failure in the main chain (validate raised,
    upload failed, network down). The originating error is attached
    via `__cause__`.
    """
    nodes = _build_compose_graph(text, url, auth, og_tags, langs=langs)

    @task(name="post_node", depends_on=[nodes["record_node"]])
    def post_node(record_node):
        return create_post(record_node, auth)

    flow = Flow(post_node, max_workers=3)
    flow.run()

    post_state = flow.results.get(post_node.name)
    if post_state is None or post_state.state != StepState.SUCCEEDED:
        for r in flow.results.values():
            if r.state == StepState.FAILED and r.error is not None:
                raise RuntimeError(
                    f"compose_link_post failed at {r.name}: {r.error}"
                ) from r.error
        raise RuntimeError(
            f"compose_link_post: post_node ended in "
            f"{post_state.state.value if post_state else 'missing'}"
        )

    def _val(td):
        r = flow.results.get(td.name)
        if r is None or r.state != StepState.SUCCEEDED:
            return None
        return r.value

    return {
        "record": _val(nodes["record_node"]),
        "post": _val(post_node),
        "og_tags": _val(nodes["fetch_og"]),
        "thumb_blob": _val(nodes["upload_blob_node"]),
        "facets": _val(nodes["facets_node"]),
        "detached_failures": [],
    }


def create_post(record, auth):
    """Submit a post record to Bluesky.

    Returns dict with uri, cid, url, rkey.
    """
    data = json.dumps({
        "repo": auth["did"],
        "collection": "app.bsky.feed.post",
        "record": record
    }).encode()

    req = urllib.request.Request(
        "https://bsky.social/xrpc/com.atproto.repo.createRecord",
        data=data, method="POST",
        headers={
            "Authorization": f"Bearer {auth['access_jwt']}",
            "Content-Type": "application/json"
        }
    )
    result = json.loads(urllib.request.urlopen(req).read())

    post_uri = result["uri"]
    rkey = post_uri.split("/")[-1]
    handle = auth.get("handle", auth["did"])
    bsky_url = f"https://bsky.app/profile/{handle}/post/{rkey}"

    print(f"  ✓ Posted: {bsky_url}")
    return {
        "uri": post_uri,
        "cid": result["cid"],
        "url": bsky_url,
        "rkey": rkey
    }

# ── Lightweight interactions ───────────────────────────────────────

def like(subject_uri, subject_cid, auth):
    """Like a Bluesky post — the lightest acknowledgment available.

    Prefer a like over a reply when a reply would be unwelcome or add
    nothing: an interlocutor who has signalled they'd rather not engage,
    a thread that's already resolved, or a post you want to acknowledge
    without demanding a further turn. A like asks nothing of the recipient.

    `subject_uri` / `subject_cid` are the AT-URI and CID of the post being
    liked (both are required by app.bsky.feed.like; the CID pins the exact
    version). Returns the like record's own uri/cid/rkey — pass the uri to
    `unlike` to reverse it.
    """
    data = json.dumps({
        "repo": auth["did"],
        "collection": "app.bsky.feed.like",
        "record": {
            "$type": "app.bsky.feed.like",
            "subject": {"uri": subject_uri, "cid": subject_cid},
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
    }).encode()

    req = urllib.request.Request(
        "https://bsky.social/xrpc/com.atproto.repo.createRecord",
        data=data, method="POST",
        headers={
            "Authorization": f"Bearer {auth['access_jwt']}",
            "Content-Type": "application/json",
        },
    )
    result = json.loads(urllib.request.urlopen(req).read())

    like_uri = result["uri"]
    print(f"  \u2665 Liked: {subject_uri}")
    return {
        "uri": like_uri,
        "cid": result["cid"],
        "rkey": like_uri.split("/")[-1],
    }


def unlike(like_uri, auth):
    """Remove a like by deleting its record. `like_uri` is from `like()`."""
    data = json.dumps({
        "repo": auth["did"],
        "collection": "app.bsky.feed.like",
        "rkey": like_uri.split("/")[-1],
    }).encode()

    req = urllib.request.Request(
        "https://bsky.social/xrpc/com.atproto.repo.deleteRecord",
        data=data, method="POST",
        headers={
            "Authorization": f"Bearer {auth['access_jwt']}",
            "Content-Type": "application/json",
        },
    )
    urllib.request.urlopen(req).read()
    print(f"  \u2661 Unliked: {like_uri}")
    return {"deleted": like_uri}


# \u2500\u2500 Session auth + record deletion \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# The library API above takes a pre-resolved `auth` dict \u2014 correct for a
# library, but it leaves no way to invoke the tool as the manifest declares
# (`python -m muninn_utils.bsky_card <action>`, see
# manifests/bsky-card/muninn-bsky-card.v0.4.json). The helpers below resolve
# auth from a handle + app password so the CLI (issue #66) can run standalone.

_PDS_DEFAULT = "https://bsky.social"


def _pds_base():
    """PDS base URL for atproto calls. Override with BSKY_PDS; default bsky.social."""
    return os.environ.get("BSKY_PDS", _PDS_DEFAULT).rstrip("/")


def create_session(handle, password, pds=None):
    """com.atproto.server.createSession \u2192 auth dict.

    Returns {access_jwt, did, handle, pds} \u2014 the same `auth` shape the rest of
    this module consumes, plus the resolved PDS for reporting.
    """
    pds = (pds or _pds_base()).rstrip("/")
    payload = json.dumps({"identifier": handle, "password": password}).encode()
    req = urllib.request.Request(
        f"{pds}/xrpc/com.atproto.server.createSession",
        data=payload, method="POST",
        headers={"Content-Type": "application/json"},
    )
    session = json.loads(urllib.request.urlopen(req).read())
    return {
        "access_jwt": session["accessJwt"],
        "did": session["did"],
        "handle": session["handle"],
        "pds": pds,
    }


def resolve_handle(handle, pds=None):
    """com.atproto.identity.resolveHandle \u2192 DID string."""
    from urllib.parse import quote
    pds = (pds or _pds_base()).rstrip("/")
    resp = urllib.request.urlopen(
        f"{pds}/xrpc/com.atproto.identity.resolveHandle?handle={quote(handle)}"
    )
    return json.loads(resp.read())["did"]


def delete_post(uri, auth):
    """com.atproto.repo.deleteRecord on a post AT-URI. Idempotent.

    `uri` is an at:// URI as returned by create_post (e.g.
    at://did:plc:.../app.bsky.feed.post/<rkey>). Deletes from the
    authenticated repo; deleting a non-existent record is a no-op.
    Returns {uri, deleted: True}.
    """
    m = re.match(r"at://[^/]+/([^/]+)/(.+)", uri)
    if not m:
        raise ValueError(f"Not an at:// post URI: {uri!r}")
    collection, rkey = m.group(1), m.group(2)
    data = json.dumps({
        "repo": auth["did"],
        "collection": collection,
        "rkey": rkey,
    }).encode()
    req = urllib.request.Request(
        f"{_pds_base()}/xrpc/com.atproto.repo.deleteRecord",
        data=data, method="POST",
        headers={
            "Authorization": f"Bearer {auth['access_jwt']}",
            "Content-Type": "application/json",
        },
    )
    urllib.request.urlopen(req).read()
    return {"uri": uri, "deleted": True}


# \u2500\u2500 CLI entrypoint (issue #66) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# `python -m muninn_utils.bsky_card <action>` mirrors the manifest's three
# actions: whoami (no input), post-link (stdin JSON), delete-post (stdin JSON).
# Every action emits a single JSON object on stdout. Library progress prints
# are redirected to stderr so stdout stays pure JSON; failures emit the
# manifest's "standard" error envelope: {"error": {"code", "message"}}.

class _CliError(Exception):
    """Maps a failure to a manifest error code + human message."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _error_envelope(code, message):
    return {"error": {"code": code, "message": message}}


def _cli_auth():
    """Resolve a session from BSKY_HANDLE + BSKY_APP_PASSWORD."""
    handle = os.environ.get("BSKY_HANDLE")
    password = os.environ.get("BSKY_APP_PASSWORD")
    if not handle or not password:
        raise _CliError(
            "auth_invalid",
            "Set BSKY_HANDLE and BSKY_APP_PASSWORD in the environment.",
        )
    try:
        return create_session(handle, password)
    except urllib.error.HTTPError as e:
        if e.code in (400, 401):
            raise _CliError("auth_invalid",
                            f"createSession rejected the credentials (HTTP {e.code}).")
        raise
    except urllib.error.URLError as e:
        raise _CliError("network_unreachable",
                        f"Could not reach the PDS: {getattr(e, 'reason', e)}")


def _action_whoami(_payload):
    """Authenticate, confirm the handle resolves to a DID, return {handle, did, pds}."""
    auth = _cli_auth()
    try:
        resolved_did = resolve_handle(auth["handle"], pds=auth.get("pds"))
    except urllib.error.HTTPError as e:
        raise _CliError("handle_not_found",
                        f"resolveHandle failed for {auth['handle']} (HTTP {e.code}).")
    except urllib.error.URLError as e:
        raise _CliError("network_unreachable",
                        f"Could not reach the PDS: {getattr(e, 'reason', e)}")
    out = {"handle": auth["handle"], "did": auth["did"], "pds": auth.get("pds", _pds_base())}
    # The session DID is authoritative; surface a mismatch rather than hide it.
    if resolved_did != auth["did"]:
        out["did_mismatch"] = resolved_did
    return out


def _action_post_link(payload):
    """Post a URL with a link card. stdin: {text, url, og_overrides?, languages?}."""
    if not isinstance(payload, dict):
        raise _CliError("error", "post-link expects a JSON object on stdin.")
    text = payload.get("text")
    url = payload.get("url")
    if not text or not url:
        raise _CliError("error", "post-link requires both 'text' and 'url'.")

    # Grapheme-budget pre-check mirrors the library's 300-cap contract, measured
    # on the post-shaping text (markdown stripped, URL appended) AT Proto counts.
    composed = final_text_for_post(text, url)
    try:
        from bsky_limit import fits as _fits, BSKY_LIMIT as _limit
    except Exception:
        _fits, _limit = (lambda t: len(t) <= 300), 300
    if not _fits(composed):
        raise _CliError(
            "text_too_long",
            f"text exceeds {_limit} graphemes after markdown strip + URL append.",
        )

    og_tags = None
    overrides = payload.get("og_overrides")
    if overrides:
        og_tags = {"url": url}
        for k in ("title", "description", "image"):
            if overrides.get(k) is not None:
                og_tags[k] = overrides[k]

    langs = payload.get("languages") or ["en"]
    auth = _cli_auth()
    try:
        result = compose_link_post(text, url, auth, og_tags=og_tags, langs=langs)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise _CliError("rate_limited", "Bluesky rate limit hit (HTTP 429).")
        if e.code in (400, 401):
            raise _CliError("auth_invalid", f"createRecord rejected (HTTP {e.code}).")
        raise
    except urllib.error.URLError as e:
        raise _CliError("url_unreachable", f"Network error during post: {getattr(e, 'reason', e)}")
    post = result["post"]
    return {"uri": post["uri"], "cid": post["cid"], "url": post["url"]}


def _action_delete_post(payload):
    """Delete a post by AT-URI. stdin: {uri}."""
    if not isinstance(payload, dict) or not payload.get("uri"):
        raise _CliError("uri_invalid", "delete-post requires a 'uri' field on stdin.")
    uri = payload["uri"]
    if not uri.startswith("at://"):
        raise _CliError("uri_invalid", f"Expected an at:// URI, got {uri!r}.")
    auth = _cli_auth()
    try:
        return delete_post(uri, auth)
    except urllib.error.HTTPError as e:
        if e.code in (400, 401):
            raise _CliError("auth_invalid", f"deleteRecord rejected (HTTP {e.code}).")
        raise
    except urllib.error.URLError as e:
        raise _CliError("network_unreachable", f"Network error during delete: {getattr(e, 'reason', e)}")


_ACTIONS = {
    "whoami": ("none", _action_whoami),
    "post-link": ("stdin", _action_post_link),
    "delete-post": ("stdin", _action_delete_post),
}


def _read_stdin_json():
    import sys
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else {}


def _main(argv):
    import sys
    import contextlib

    real_stdout = sys.stdout

    def _emit(obj):
        real_stdout.write(json.dumps(obj) + "\n")
        real_stdout.flush()

    usage = (
        "usage: python -m muninn_utils.bsky_card <"
        + "|".join(_ACTIONS)
        + ">  (post-link/delete-post read a JSON object from stdin)"
    )
    if not argv or argv[0] in ("-h", "--help"):
        _emit(_error_envelope("error", usage))
        return 2

    action = argv[0]
    entry = _ACTIONS.get(action)
    if entry is None:
        _emit(_error_envelope("error", f"unknown action {action!r}. {usage}"))
        return 2

    input_kind, fn = entry
    try:
        payload = _read_stdin_json() if input_kind == "stdin" else {}
    except json.JSONDecodeError as e:
        _emit(_error_envelope("error", f"invalid JSON on stdin: {e}"))
        return 1

    try:
        # Library helpers print progress to stdout; keep stdout pure JSON.
        with contextlib.redirect_stdout(sys.stderr):
            result = fn(payload)
    except _CliError as e:
        _emit(_error_envelope(e.code, e.message))
        return 1
    except urllib.error.HTTPError as e:
        _emit(_error_envelope("error", f"HTTP {e.code}: {e.reason}"))
        return 1
    except urllib.error.URLError as e:
        _emit(_error_envelope("network_unreachable", str(getattr(e, "reason", e))))
        return 1
    except Exception as e:  # noqa: BLE001 \u2014 last-resort envelope; never bare-crash
        _emit(_error_envelope("error", f"{type(e).__name__}: {e}"))
        return 1

    _emit(result)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
