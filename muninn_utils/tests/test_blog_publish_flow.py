"""
Tests for blog_publish.publish_and_announce flowing graph (issue #616).

Verifies:
  - main DAG order: publish_page → wait_for_deploy → update_feed
  - detached chain auto-discovery: announce_bsky → link_engagement_node
  - retry_until=lambda r: r["deployed"] consumes budget when deploy is slow
  - when= gate skips update_feed when feed_path is None
  - validate= rejects bsky_text > BSKY_LIMIT before any post fires
  - bsky failure populates detached_failures, doesn't raise

Network calls are monkeypatched. No real GitHub or Bluesky access required.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

THIS_DIR = Path(__file__).resolve().parent
PKG_DIR = THIS_DIR.parent
SKILLS_ROOT = PKG_DIR.parent

# bsky_card and bsky_limit are needed by blog_publish at import time. Stub /
# load them BEFORE adding PKG_DIR to sys.path so we don't accidentally pick up
# the materialized siblings under /root/muninn_utils.
import types

bsky_card_stub = types.ModuleType("bsky_card")
# Collapsed compose_link_post returns {record, post, og_tags, thumb_blob,
# facets, detached_failures} — see #617.
bsky_card_stub.compose_link_post = MagicMock()


def _stub_final_text_for_post(text, url):
    # Mirror of bsky_card.final_text_for_post for stub purposes (markdown
    # stripping isn't exercised here — just the URL-append fallback).
    return f"{text}\n{url}" if url not in text else text


bsky_card_stub.final_text_for_post = _stub_final_text_for_post
sys.modules["bsky_card"] = bsky_card_stub

# bsky_limit: prefer the real materialized one (correct grapheme counting),
# fall back to a tiny len-based stub.
try:
    import importlib.util
    materialized = Path("/root/muninn_utils/bsky_limit.py")
    if materialized.exists():
        spec = importlib.util.spec_from_file_location("bsky_limit", materialized)
        bsky_limit_mod = importlib.util.module_from_spec(spec)
        sys.modules["bsky_limit"] = bsky_limit_mod
        spec.loader.exec_module(bsky_limit_mod)
        bsky_limit = bsky_limit_mod
    else:
        raise FileNotFoundError
except Exception:
    bsky_limit = types.ModuleType("bsky_limit")
    bsky_limit.BSKY_LIMIT = 300
    bsky_limit.fits = lambda t, limit=300: len(t) <= limit
    sys.modules["bsky_limit"] = bsky_limit

# Wire flowing from the skill bytes (canonical source).
# Locate the flowing skill (canonical install OR a sibling clone of claude-skills)
import os as _os
for _flow_path in (
    "/mnt/skills/user/flowing/scripts",
    str(SKILLS_ROOT / "flowing" / "scripts"),
    str(PKG_DIR.parent.parent / "claude-skills" / "flowing" / "scripts"),
):
    if _os.path.isdir(_flow_path):
        sys.path.insert(0, _flow_path)
        break
else:
    raise RuntimeError("flowing skill not found in any expected location")
import flowing as _flowing
sys.modules.setdefault("flowing", _flowing)

# Now load OUR blog_publish (not the materialized one) by file path so there
# is zero ambiguity about which copy is under test.
import importlib.util
spec = importlib.util.spec_from_file_location(
    "blog_publish_under_test", PKG_DIR / "blog_publish.py"
)
bp = importlib.util.module_from_spec(spec)
sys.modules["blog_publish_under_test"] = bp
spec.loader.exec_module(bp)


def _reset(monkeypatch):
    """Patch every external call inside blog_publish to a controllable mock."""
    monkeypatch.setattr(bp, "publish_page", MagicMock(return_value="abcdef1234"))
    monkeypatch.setattr(bp, "update_feed", MagicMock(return_value="feed5678"))
    monkeypatch.setattr(bp, "link_engagement", MagicMock(return_value="link9999"))
    monkeypatch.setattr(bp, "_probe_url", MagicMock(return_value=True))

    bsky_card_stub.compose_link_post.reset_mock()
    bsky_card_stub.compose_link_post.side_effect = None
    bsky_card_stub.compose_link_post.return_value = {
        "record": {"$type": "app.bsky.feed.post"},
        "post": {
            "uri": "at://did:plc:x/app.bsky.feed.post/abc",
            "cid": "cid1",
            "url": "https://bsky.app/profile/h/post/abc",
            "rkey": "abc",
        },
        "og_tags": {"url": "u"},
        "thumb_blob": None,
        "facets": [],
        "detached_failures": [],
    }
    return bsky_card_stub


def test_happy_path_main_chain_and_detached(monkeypatch):
    """All five steps run, in order; detached chain produces post + link."""
    bc = _reset(monkeypatch)

    result = bp.publish_and_announce(
        path="blog/x.html",
        content="<html/>",  # validate_html=False below — flow shape only
        validate_html=False,
        bsky_text="A post",
        auth={"access_jwt": "j", "did": "did:plc:x", "handle": "h"},
        feed_entry={"title": "X", "summary": "..."},
    )

    assert result["page_url"] == f"{bp._MUNINN_BASE}/blog/x.html"
    assert result["commit_sha"] == "abcdef1234"
    assert result["feed_sha"] == "feed5678"
    assert result["deployed"] is True
    assert result["bsky_post"]["url"].startswith("https://bsky.app/")
    assert result["update_sha"] == "link9999"
    assert result["detached_failures"] == []

    # Main-chain functions each called exactly once.
    assert bp.publish_page.call_count == 1
    assert bp.update_feed.call_count == 1
    assert bp.link_engagement.call_count == 1
    assert bc.compose_link_post.call_count == 1


def test_when_skips_feed_update_without_feed_path(monkeypatch):
    """feed_path=None → update_feed_node skipped; detached chain still runs."""
    bc = _reset(monkeypatch)

    result = bp.publish_and_announce(
        path="blog/y.html",
        content="<html/>",  # validate_html=False below — flow shape only
        validate_html=False,
        bsky_text="B",
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
        repo="oaustegard/oaustegard.github.io",
        site_base="https://austegard.com",
        feed_path=None,
        feed_entry=None,
    )

    assert bp.update_feed.call_count == 0
    assert result["feed_sha"] is None
    # Page commit and bsky chain still ran.
    assert bp.publish_page.call_count == 1
    assert bc.compose_link_post.call_count == 1
    assert result["update_sha"] == "link9999"


def test_pre_commit_blocks_oversize_bsky_text(monkeypatch):
    """bsky_text > BSKY_LIMIT → ValueError pre-commit; NO commits land (#24)."""
    bc = _reset(monkeypatch)

    huge = "x" * (bsky_limit.BSKY_LIMIT + 1)

    import pytest
    with pytest.raises(ValueError) as exc:
        bp.publish_and_announce(
            path="blog/z.html",
            content="<html/>",  # validate_html=False below — flow shape only
            validate_html=False,
            bsky_text=huge,
            auth={"access_jwt": "j", "did": "did", "handle": "h"},
            feed_entry={"title": "Z", "summary": "..."},
        )

    # Error message names the budget.
    msg = str(exc.value).lower()
    assert "grapheme" in msg or str(bsky_limit.BSKY_LIMIT) in str(exc.value)

    # No commits or posts happened — the gate fired before flow.run().
    assert bp.publish_page.call_count == 0
    assert bp.update_feed.call_count == 0
    assert bp.link_engagement.call_count == 0
    assert bc.compose_link_post.call_count == 0


def test_pre_commit_blocks_when_url_append_pushes_over_limit(monkeypatch):
    """Raw bsky_text fits 300, but URL append pushes record.text past 300.

    Pre-#11: detached gate caught this AFTER page commit (post-deploy).
    Post-#11: detached gate measured final_text_for_post() so the budget
    violation surfaced in detached_failures, but the page still shipped.
    Post-#24: pre-commit gate raises ValueError BEFORE anything commits.
    """
    bc = _reset(monkeypatch)

    # 290 graphemes — fits 300 on its own, but URL append blows past it.
    bsky_text = "x" * 290

    import pytest
    with pytest.raises(ValueError) as exc:
        bp.publish_and_announce(
            path="blog/long.html",
            content="<html/>",  # validate_html=False below — flow shape only
            validate_html=False,
            bsky_text=bsky_text,
            auth={"access_jwt": "j", "did": "did", "handle": "h"},
            feed_entry={"title": "L", "summary": "..."},
        )

    msg = str(exc.value).lower()
    assert "grapheme" in msg or str(bsky_limit.BSKY_LIMIT) in str(exc.value)

    # No commits — the gate fires before flow.run().
    assert bp.publish_page.call_count == 0
    assert bc.compose_link_post.call_count == 0


def test_retry_until_consumes_budget_when_deploy_slow(monkeypatch):
    """First N probes return False; succeeds on attempt N+1 within retry budget."""
    bc = _reset(monkeypatch)

    # Speed up the test: monkey-patch retry config to 0ms backoff.
    monkeypatch.setattr(bp, "_DEPLOY_POLL_MS", 0)
    monkeypatch.setattr(bp, "_DEPLOY_RETRIES", 4)

    # Returns False, False, True (succeeds on third attempt).
    seq = iter([False, False, True])
    bp._probe_url = MagicMock(side_effect=lambda *a, **k: next(seq))
    monkeypatch.setattr(bp, "_probe_url", bp._probe_url)

    result = bp.publish_and_announce(
        path="blog/r.html",
        content="<html/>",  # validate_html=False below — flow shape only
        validate_html=False,
        bsky_text="R",
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
        feed_entry={"title": "R", "summary": "..."},
    )

    assert result["deployed"] is True
    # Probe called at least 3 times (the first two returned False).
    assert bp._probe_url.call_count == 3
    # Downstream still happened.
    assert bp.update_feed.call_count == 1
    assert bc.compose_link_post.call_count == 1


def test_retry_until_exhausts_budget(monkeypatch):
    """Deploy never lands → wait_for_deploy_node FAILS, downstream all skipped."""
    bc = _reset(monkeypatch)

    monkeypatch.setattr(bp, "_DEPLOY_POLL_MS", 0)
    monkeypatch.setattr(bp, "_DEPLOY_RETRIES", 2)
    monkeypatch.setattr(bp, "_probe_url", MagicMock(return_value=False))

    result = bp.publish_and_announce(
        path="blog/never.html",
        content="<html/>",  # validate_html=False below — flow shape only
        validate_html=False,
        bsky_text="N",
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
        feed_entry={"title": "N", "summary": "..."},
    )

    # Page committed, but everything downstream skipped.
    assert result["commit_sha"] == "abcdef1234"
    assert result["deployed"] is False
    assert result["feed_sha"] is None
    assert result["bsky_post"] is None
    assert result["update_sha"] is None
    assert bp.update_feed.call_count == 0
    assert bc.compose_link_post.call_count == 0


def test_skip_deploy_wait_short_circuits_probe(monkeypatch):
    """skip_deploy_wait=True → _probe_url never called."""
    bc = _reset(monkeypatch)
    monkeypatch.setattr(bp, "_probe_url", MagicMock(return_value=False))

    result = bp.publish_and_announce(
        path="blog/skip.html",
        content="<html/>",  # validate_html=False below — flow shape only
        validate_html=False,
        bsky_text="S",
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
        feed_entry={"title": "S", "summary": "..."},
        skip_deploy_wait=True,
    )

    assert result["deployed"] is True
    assert bp._probe_url.call_count == 0
    assert bp.update_feed.call_count == 1
    assert bc.compose_link_post.call_count == 1


def test_bsky_failure_does_not_block_main_return(monkeypatch):
    """compose_link_post raises → bsky_post is None, detached_failures populated, but feed/page ok."""
    bc = _reset(monkeypatch)
    bc.compose_link_post.side_effect = RuntimeError("AT Proto 503")

    result = bp.publish_and_announce(
        path="blog/det.html",
        content="<html/>",  # validate_html=False below — flow shape only
        validate_html=False,
        bsky_text="D",
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
        feed_entry={"title": "D", "summary": "..."},
    )

    assert result["commit_sha"] == "abcdef1234"
    assert result["feed_sha"] == "feed5678"
    assert result["bsky_post"] is None
    assert result["update_sha"] is None
    failures = dict(result["detached_failures"])
    assert "announce_bsky" in failures
    assert "503" in failures["announce_bsky"]


def test_reindex_runs_as_detached_step(monkeypatch):
    """A reindex callable runs after deploy; its return surfaces as result['reindexed']."""
    _reset(monkeypatch)
    reindex = MagicMock(return_value={"index_version": "c607ec4b603b"})

    result = bp.publish_and_announce(
        path="blog/r.html",
        content="<html/>",
        validate_html=False,
        bsky_text="R",
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
        feed_entry={"title": "R", "summary": "..."},
        reindex=reindex,
    )

    assert reindex.call_count == 1
    assert result["reindexed"] == {"index_version": "c607ec4b603b"}
    assert result["detached_failures"] == []
    # the page/bsky chain is unaffected
    assert result["commit_sha"] == "abcdef1234"
    assert result["bsky_post"]["url"].startswith("https://bsky.app/")


def test_reindex_absent_by_default(monkeypatch):
    """No reindex callable → no reindex node, result['reindexed'] is None."""
    _reset(monkeypatch)
    result = bp.publish_and_announce(
        path="blog/r.html",
        content="<html/>",
        validate_html=False,
        bsky_text="R",
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
        feed_entry={"title": "R", "summary": "..."},
    )
    assert result["reindexed"] is None


def test_reindex_failure_does_not_block_main_return(monkeypatch):
    """reindex raises → reindexed is None, failure is detached, page/bsky still succeed."""
    _reset(monkeypatch)
    reindex = MagicMock(side_effect=RuntimeError("KV PUT 500"))

    result = bp.publish_and_announce(
        path="blog/r.html",
        content="<html/>",
        validate_html=False,
        bsky_text="R",
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
        feed_entry={"title": "R", "summary": "..."},
        reindex=reindex,
    )

    assert result["commit_sha"] == "abcdef1234"
    assert result["bsky_post"]["url"].startswith("https://bsky.app/")
    assert result["reindexed"] is None
    failures = dict(result["detached_failures"])
    assert "reindex_node" in failures
    assert "KV PUT 500" in failures["reindex_node"]


# ── validate_blog_html (issue #20) ──────────────────────────────────

import pytest


def _valid_html(article_extra: str = '<img src="/static/hero.png" alt="Hero">') -> str:
    """A minimal post that passes every check in validate_blog_html()."""
    return f"""<!doctype html>
<html><head>
<meta property="article:published_time" content="2026-05-13T12:00:00Z">
<meta name="bsky:uri" content="">
<meta property="og:image" content="https://muninn.austegard.com/static/hero.png">
</head><body>
<article>
<p class="post-meta">2026-05-13 · Muninn</p>
{article_extra}
<p>Post body.</p>
</article>
</body></html>"""


@pytest.fixture
def patch_path_exists(monkeypatch):
    """Default: every asset exists. Tests can override via .return_value."""
    mock = MagicMock(return_value=True)
    monkeypatch.setattr(bp, "_gh_path_exists", mock)
    return mock


def test_validate_blog_html_happy_path(patch_path_exists):
    """A well-formed post passes all six checks; asset existence probed once."""
    bp.validate_blog_html(_valid_html(), repo="oaustegard/muninn.austegard.com")
    assert patch_path_exists.call_count == 1
    args = patch_path_exists.call_args
    assert args[0][1] == "static/hero.png"


def test_validate_blog_html_missing_published_time(patch_path_exists):
    html = _valid_html().replace(
        '<meta property="article:published_time" content="2026-05-13T12:00:00Z">', "")
    with pytest.raises(ValueError, match="article:published_time"):
        bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_unparseable_published_time(patch_path_exists):
    html = _valid_html().replace(
        '"2026-05-13T12:00:00Z"', '"not-a-date"')
    with pytest.raises(ValueError, match="not a parseable ISO"):
        bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_wrong_byline_class(patch_path_exists):
    html = _valid_html().replace('class="post-meta"', 'class="byline"')
    with pytest.raises(ValueError, match="post-meta"):
        bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_missing_bsky_uri_stub(patch_path_exists):
    html = _valid_html().replace(
        '<meta name="bsky:uri" content="">', "")
    with pytest.raises(ValueError, match="bsky:uri"):
        bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_og_image_without_inline_img(patch_path_exists):
    """og:image set, but article body has no <img> — past tg-cli-for-tangled bug."""
    html = _valid_html(article_extra="")  # no <img> in article
    with pytest.raises(ValueError, match="no <img>.*article body"):
        bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_og_image_asset_missing(patch_path_exists):
    """og:image points at this repo's domain but the asset isn't there."""
    patch_path_exists.return_value = False
    with pytest.raises(ValueError, match="does not exist"):
        bp.validate_blog_html(_valid_html(), repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_og_image_external_skips_existence(monkeypatch):
    """External CDN og:image — inline <img> still required, but no existence probe."""
    mock = MagicMock(return_value=False)
    monkeypatch.setattr(bp, "_gh_path_exists", mock)
    html = _valid_html().replace(
        "https://muninn.austegard.com/static/hero.png",
        "https://cdn.example.com/hero.png",
    )
    bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")
    assert mock.call_count == 0  # external host → no probe


def test_validate_blog_html_og_image_relative_path(monkeypatch):
    """og:image as relative path: probe against `repo` directly."""
    mock = MagicMock(return_value=True)
    monkeypatch.setattr(bp, "_gh_path_exists", mock)
    html = _valid_html().replace(
        "https://muninn.austegard.com/static/hero.png",
        "/static/hero.png",
    )
    bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")
    assert mock.call_args[0][1] == "static/hero.png"


def test_validate_blog_html_no_og_image_skips_checks_4_5(monkeypatch):
    """Post without og:image: checks 4 and 5 skipped; no probe call."""
    mock = MagicMock(return_value=False)
    monkeypatch.setattr(bp, "_gh_path_exists", mock)
    html = _valid_html(article_extra="").replace(
        '<meta property="og:image" content="https://muninn.austegard.com/static/hero.png">',
        "",
    )
    bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")
    assert mock.call_count == 0


def test_validate_blog_html_img_missing_alt(patch_path_exists):
    """An <img> tag without alt="…" — a11y regression."""
    html = _valid_html(article_extra='<img src="/static/hero.png">')
    with pytest.raises(ValueError, match="missing non-empty alt"):
        bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_img_with_empty_alt(patch_path_exists):
    """alt="" treated as missing — explicit decorative-image opt-in not supported here."""
    html = _valid_html(article_extra='<img src="/static/hero.png" alt="">')
    with pytest.raises(ValueError, match="missing non-empty alt"):
        bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


# ── Check 7: HTML entities in social-card meta content ──────────────

_CARD_META = (
    '<title>Clean title</title>\n'
    '<meta name="description" content="Clean description.">\n'
    '<meta name="article:summary" content="Clean summary.">\n'
    '<meta property="og:title" content="Clean og:title">\n'
    '<meta property="og:description" content="Clean og:description.">\n'
)


def _valid_html_with_card() -> str:
    """_valid_html() augmented with all five card-surfaced meta fields."""
    return _valid_html().replace(
        '<meta property="article:published_time"',
        _CARD_META + '<meta property="article:published_time"',
    )


def test_validate_blog_html_card_fields_unicode_happy_path(patch_path_exists):
    """All five card fields present with Unicode punctuation — passes."""
    html = _valid_html_with_card().replace(
        "Clean og:title", "I don\u2019t have a watch."
    ).replace(
        "Clean og:description", "I wrote \u2018a month ago\u2019 in a post."
    )
    bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_entity_in_og_title(patch_path_exists):
    """`&rsquo;` in og:title → raise (i-dont-have-a-watch failure mode)."""
    html = _valid_html_with_card().replace(
        "Clean og:title", "I don&rsquo;t have a watch."
    )
    with pytest.raises(ValueError, match=r"og:title.*&rsquo;|&rsquo;.*og:title"):
        bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_entity_in_og_description(patch_path_exists):
    """`&lsquo;` / `&rsquo;` in og:description → raise."""
    html = _valid_html_with_card().replace(
        "Clean og:description", "I wrote &lsquo;a month ago&rsquo; in a post."
    )
    with pytest.raises(ValueError, match=r"og:description"):
        bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_entity_in_title_tag(patch_path_exists):
    """`&rsquo;` in <title> → raise (also surfaces on the card)."""
    html = _valid_html_with_card().replace(
        "Clean title", "I don&rsquo;t have a watch."
    )
    with pytest.raises(ValueError, match=r"<title>"):
        bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_entity_in_description(patch_path_exists):
    """`&rsquo;` in <meta name="description"> → raise."""
    html = _valid_html_with_card().replace(
        "Clean description.", "yesterday&rsquo;s 12-hour work."
    )
    with pytest.raises(ValueError, match=r'name="description"'):
        bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_entity_in_article_summary(patch_path_exists):
    """`&rsquo;` in <meta name="article:summary"> → raise."""
    html = _valid_html_with_card().replace(
        "Clean summary.", "yesterday&rsquo;s 12-hour work."
    )
    with pytest.raises(ValueError, match=r'article:summary'):
        bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_amp_entity_allowed_in_card(patch_path_exists):
    """`&amp;` is structurally required in HTML and must be allowed."""
    html = _valid_html_with_card().replace(
        "Clean og:title", "Tom &amp; Jerry"
    ).replace(
        "Clean og:description", "Cats &amp; dogs and other pairs."
    )
    bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_quot_lt_gt_entities_allowed_in_card(patch_path_exists):
    """`&lt;`, `&gt;`, `&quot;` are structural and allowed."""
    html = _valid_html_with_card().replace(
        "Clean og:title", "How &lt;script&gt; is escaped"
    ).replace(
        "Clean og:description", "Use the &quot;right&quot; thing."
    )
    bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_numeric_entity_in_og_title(patch_path_exists):
    """`&#8217;` (numeric U+2019) in og:title → raise. Type Unicode directly."""
    html = _valid_html_with_card().replace(
        "Clean og:title", "I don&#8217;t have a watch."
    )
    with pytest.raises(ValueError, match=r"og:title"):
        bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_hex_entity_in_og_description(patch_path_exists):
    """`&#x2019;` (hex numeric) in og:description → raise."""
    html = _valid_html_with_card().replace(
        "Clean og:description", "I wrote &#x2018;a month ago&#x2019; today."
    )
    with pytest.raises(ValueError, match=r"og:description"):
        bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_entity_in_body_is_fine(patch_path_exists):
    """Entities in visible body text are normal HTML and must NOT raise."""
    # Add entities only to article body, leave card meta fields clean.
    html = _valid_html_with_card().replace(
        "<p>Post body.</p>",
        "<p>I don&rsquo;t have a watch &mdash; just &ldquo;vibes.&rdquo;</p>",
    )
    bp.validate_blog_html(html, repo="oaustegard/muninn.austegard.com")


def test_validate_blog_html_no_card_fields_skips_check_7(patch_path_exists):
    """Posts without card meta tags pass check 7 silently (regression guard)."""
    # _valid_html() has no <title>/og:title/og:description/description/summary
    # so check 7 should find nothing to inspect and pass.
    bp.validate_blog_html(_valid_html(), repo="oaustegard/muninn.austegard.com")


def test_publish_and_announce_validates_before_committing(monkeypatch):
    """validate_html=True (default): bad HTML raises BEFORE any flow task runs."""
    _reset(monkeypatch)
    monkeypatch.setattr(bp, "_gh_path_exists", MagicMock(return_value=True))

    bad_html = "<html><body>no metadata at all</body></html>"
    with pytest.raises(ValueError, match="article:published_time"):
        bp.publish_and_announce(
            path="blog/bad.html",
            content=bad_html,
            bsky_text="x",
            auth={"access_jwt": "j", "did": "d", "handle": "h"},
            feed_entry={"title": "Bad", "summary": "..."},
        )
    # No side effects: publish_page never reached.
    assert bp.publish_page.call_count == 0


def test_publish_and_announce_validate_html_false_bypasses(monkeypatch):
    """validate_html=False: pre-flow check skipped; existing flow path used."""
    bc = _reset(monkeypatch)
    result = bp.publish_and_announce(
        path="blog/bypass.html",
        content="<html/>",  # would fail validation
        validate_html=False,
        bsky_text="x",
        auth={"access_jwt": "j", "did": "d", "handle": "h"},
        feed_entry={"title": "Bypass", "summary": "..."},
    )
    assert result["commit_sha"] == "abcdef1234"
    assert bc.compose_link_post.call_count == 1


def test_publish_and_announce_validates_real_html_happy_path(monkeypatch):
    """validate_html=True + well-formed HTML: full pipeline runs."""
    bc = _reset(monkeypatch)
    monkeypatch.setattr(bp, "_gh_path_exists", MagicMock(return_value=True))
    result = bp.publish_and_announce(
        path="blog/good.html",
        content=_valid_html(),
        bsky_text="x",
        auth={"access_jwt": "j", "did": "d", "handle": "h"},
        feed_entry={"title": "Good", "summary": "..."},
    )
    assert result["commit_sha"] == "abcdef1234"
    assert bc.compose_link_post.call_count == 1


# ── publish_page binary content (issue #31) ────────────────────────


def _capture_gh_api(captured):
    """Build a fake `_gh_api` that records calls and returns plausible shapes."""
    def fake(method, endpoint, data=None):
        captured.append((method, endpoint, data))
        if endpoint.endswith("/git/refs/heads/main") and method == "GET":
            return {"object": {"sha": "ref_sha"}}
        if "/git/commits/" in endpoint and method == "GET":
            return {"tree": {"sha": "tree_sha"}}
        if endpoint.endswith("/git/blobs"):
            return {"sha": "blob_sha"}
        if endpoint.endswith("/git/trees"):
            return {"sha": "new_tree_sha"}
        if endpoint.endswith("/git/commits") and method == "POST":
            return {"sha": "new_commit_sha"}
        if endpoint.endswith("/git/refs/heads/main") and method == "PATCH":
            return {}
        return {}
    return fake


def test_publish_page_str_uses_utf8_encoding(monkeypatch):
    """str content → blobs API receives encoding=utf-8 and the string verbatim."""
    captured = []
    monkeypatch.setattr(bp, "_gh_api", _capture_gh_api(captured))

    sha = bp.publish_page("owner/repo", "page.html", "<html>hi</html>")
    assert sha == "new_commit_sha"

    blob_calls = [c for c in captured if c[1].endswith("/git/blobs")]
    assert len(blob_calls) == 1
    payload = blob_calls[0][2]
    assert payload == {"content": "<html>hi</html>", "encoding": "utf-8"}


def test_publish_page_bytes_uses_base64_encoding(monkeypatch):
    """bytes content → blobs API receives encoding=base64 and b64(content).

    Regression for issue #31: the previous hardcoded utf-8 path stored
    the base64 text of a binary file as the file body, bloating it ~4/3
    and breaking image rendering.
    """
    import base64 as _b64

    captured = []
    monkeypatch.setattr(bp, "_gh_api", _capture_gh_api(captured))

    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    sha = bp.publish_page("owner/repo", "img.png", png_bytes)
    assert sha == "new_commit_sha"

    blob_calls = [c for c in captured if c[1].endswith("/git/blobs")]
    assert len(blob_calls) == 1
    payload = blob_calls[0][2]
    assert payload["encoding"] == "base64"
    assert _b64.b64decode(payload["content"]) == png_bytes


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
