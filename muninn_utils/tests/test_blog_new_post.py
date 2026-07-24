"""
Tests for blog_publish.new_post template-filler (issue #67).

Verifies the contract from the issue:
  - Fetches blog/_template.html (monkeypatched here) and fills it
  - Returns HTML that passes validate_blog_html BY CONSTRUCTION
  - Raises (no silent freehand fallback) if the template fetch fails
  - og:image handling: set → real meta + asset-existence check; absent → strip
  - Card fields (title/summary/description) refuse non-structural HTML entities
  - Literal Unicode in card fields is preserved, not entity-encoded
  - Template is cached per (repo, ref) for the session

No real network access: _gh_raw and _gh_path_exists are monkeypatched, and the
template is an inline fixture mirroring blog/_template.html.
"""
from __future__ import annotations

import re
import sys
import types
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

THIS_DIR = Path(__file__).resolve().parent
PKG_DIR = THIS_DIR.parent

# blog_publish imports bsky_card, bsky_limit, flowing at module load. Stub the
# first two; load the real flowing. Mirrors test_blog_publish_flow.py.
bsky_card_stub = types.ModuleType("bsky_card")
bsky_card_stub.compose_link_post = MagicMock()
bsky_card_stub.final_text_for_post = lambda t, u: f"{t}\n{u}" if u not in t else t
sys.modules["bsky_card"] = bsky_card_stub

bsky_limit_stub = types.ModuleType("bsky_limit")
bsky_limit_stub.BSKY_LIMIT = 300
bsky_limit_stub.fits = lambda t, limit=300: len(t) <= limit
sys.modules["bsky_limit"] = bsky_limit_stub

import importlib.util

_flowing_spec = importlib.util.spec_from_file_location(
    "flowing", PKG_DIR / "flowing.py")
flowing = importlib.util.module_from_spec(_flowing_spec)
sys.modules["flowing"] = flowing
_flowing_spec.loader.exec_module(flowing)

_bp_spec = importlib.util.spec_from_file_location(
    "blog_publish", PKG_DIR / "blog_publish.py")
blog_publish = importlib.util.module_from_spec(_bp_spec)
sys.modules["blog_publish"] = blog_publish
_bp_spec.loader.exec_module(blog_publish)


# Inline fixture mirroring blog/_template.html (the placeholders new_post fills).
TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="ai-disclosure" content="ai-generated">

    <title>Post Title Here</title>
    <meta name="description" content="A short summary for search engines and the blog index.">
    <meta name="article:published_time" content="2026-01-01T00:00:00Z">

    <meta name="article:author" content="Oskar Austegard">
    <meta name="article:summary" content="Summary shown on the blog index page.">

    <meta property="og:title" content="Post Title Here">
    <meta property="og:description" content="A short summary for search engines and the blog index.">
    <meta property="og:type" content="article">
    <!-- og:image is optional; omit if no hero image -->
    <meta property="og:image" content="/images/blog/my-post/hero.png">

    <meta name="bsky:uri" content="at://did:plc:.../app.bsky.feed.post/...">

    <link rel="stylesheet" href="/styles/blog.css">
</head>
<body>
    <a href="/blog/" class="back-link">Blog</a>
    <article>

<h1>Post Title Here</h1>
<p class="post-meta">Written by Author &middot; Month Day, Year</p>

<!-- Post content goes here -->
<p>First paragraph...</p>

    </article>
</body>
</html>
"""

REPO = "oaustegard/muninn.austegard.com"


@pytest.fixture(autouse=True)
def patch_network(monkeypatch):
    """Stub template fetch + asset-existence; reset the per-session cache."""
    monkeypatch.setattr(blog_publish, "_gh_raw",
                        lambda repo, path, ref="main": TEMPLATE)
    assets: set = set()
    monkeypatch.setattr(blog_publish, "_gh_path_exists",
                        lambda repo, path, ref="main": path in assets)
    blog_publish._TEMPLATE_CACHE.clear()
    yield assets
    blog_publish._TEMPLATE_CACHE.clear()


def test_happy_path_no_hero():
    html = blog_publish.new_post(
        "Test Title", "A clean summary.",
        "<p>Body para one.</p><h2>Section</h2><p>Two.</p>",
        published="2026-06-22T12:00:00Z")
    assert "<title>Test Title</title>" in html
    assert "<h1>Test Title</h1>" in html
    assert 'og:title" content="Test Title"' in html
    assert 'article:published_time" content="2026-06-22T12:00:00Z"' in html
    assert 'class="post-meta">Written by Muninn \u00b7 June 22, 2026</p>' in html
    assert "<p>Body para one.</p>" in html
    assert 'name="bsky:uri" content=""' in html
    # placeholders fully consumed
    assert "Post Title Here" not in html
    assert "First paragraph..." not in html
    # og:image meta stripped when no hero (comment may remain; the tag must not)
    assert 'property="og:image"' not in html


def test_returns_validator_clean_by_construction(monkeypatch):
    # new_post calls validate_blog_html internally; a spy confirms it ran and
    # was passed the assembled HTML + repo.
    calls = []
    real = blog_publish.validate_blog_html
    monkeypatch.setattr(blog_publish, "validate_blog_html",
                        lambda c, r, b="main": (calls.append((r, b)), real(c, r, b))[1])
    blog_publish.new_post("T", "S", "<p>x</p>", published="2026-06-22T12:00:00Z")
    assert calls and calls[0][0] == REPO


def test_og_image_present_and_asset_exists(patch_network):
    patch_network.add("images/blog/x/hero.png")
    html = blog_publish.new_post(
        "Hero Post", "Sum.",
        '<p>Intro.</p><img src="/images/blog/x/hero.png" alt="A hero">',
        og_image="/images/blog/x/hero.png",
        published="2026-06-22T12:00:00Z")
    assert 'og:image" content="/images/blog/x/hero.png"' in html
    assert '<img src="/images/blog/x/hero.png" alt="A hero">' in html


def test_og_image_asset_missing_raises():
    with pytest.raises(ValueError, match="does not exist"):
        blog_publish.new_post(
            "P", "S", '<p>x</p><img src="/missing.png" alt="m">',
            og_image="/missing.png", published="2026-06-22T12:00:00Z")


def test_og_image_without_inline_img_raises(patch_network):
    patch_network.add("images/h.png")
    with pytest.raises(ValueError, match="no <img>"):
        blog_publish.new_post(
            "P", "S", "<p>no image here</p>", og_image="/images/h.png",
            published="2026-06-22T12:00:00Z")


def test_entity_in_title_refused_naming_field():
    with pytest.raises(ValueError, match=r"title.*&rsquo;"):
        blog_publish.new_post(
            "Don&rsquo;t", "S", "<p>x</p>", published="2026-06-22T12:00:00Z")


def test_template_fetch_failure_no_fallback(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("404 Not Found")
    monkeypatch.setattr(blog_publish, "_gh_raw", boom)
    blog_publish._TEMPLATE_CACHE.clear()
    with pytest.raises(ValueError, match="refuses to freehand"):
        blog_publish.new_post("P", "S", "<p>x</p>")


def test_default_published_time_is_now_and_parseable():
    html = blog_publish.new_post("P", "S", "<p>x</p>")
    m = re.search(r'article:published_time" content="([^"]+)"', html)
    assert m
    # parseable ISO — would otherwise fail validator check 1
    datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))


def test_unicode_in_card_fields_preserved():
    html = blog_publish.new_post(
        "P", "It\u2019s an em\u2014dash \u201cquote\u201d test", "<p>x</p>")
    assert "It\u2019s an em\u2014dash" in html
    assert "&rsquo;" not in html and "&mdash;" not in html


def test_ampersand_escaped_in_attr_literal_in_h1():
    html = blog_publish.new_post("Cats & Dogs", "S", "<p>x</p>")
    assert "<title>Cats &amp; Dogs</title>" in html
    assert "<h1>Cats & Dogs</h1>" in html


def test_invalid_published_raises():
    with pytest.raises(ValueError, match="not a parseable ISO"):
        blog_publish.new_post("P", "S", "<p>x</p>", published="not-a-date")


def test_template_cached_per_session(monkeypatch):
    n = {"count": 0}

    def counting_raw(repo, path, ref="main"):
        n["count"] += 1
        return TEMPLATE
    monkeypatch.setattr(blog_publish, "_gh_raw", counting_raw)
    blog_publish._TEMPLATE_CACHE.clear()
    blog_publish.new_post("A", "S", "<p>x</p>")
    blog_publish.new_post("B", "S", "<p>y</p>")
    assert n["count"] == 1  # second call hit the cache


def test_description_override_differs_from_summary():
    html = blog_publish.new_post(
        "P", "Index summary text", "<p>x</p>",
        description="SEO meta description",
        published="2026-06-22T12:00:00Z")
    assert 'name="description" content="SEO meta description"' in html
    assert 'name="article:summary" content="Index summary text"' in html
    assert 'og:description" content="SEO meta description"' in html
