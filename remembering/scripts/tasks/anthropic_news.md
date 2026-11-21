## Task: Anthropic news (claude.com/blog watcher)

You are checking https://claude.com/blog for posts published since the last
perch. This is **Oskar-facing operational signal** — distinct from zeitgeist
(which is your world-model update, raven-facing). Surface only what's new;
omit the section entirely if nothing is new. Silence is the signal.

This task is intentionally small. The full briefing is the post itself,
linked from the report. Your job is detection + one-sentence framing per post.

### Phase 0: Read state

```python
from muninn_utils.news_watch import (
    parse_claude_blog, filter_new, get_last_seen, set_last_seen,
    format_for_report, BLOG_URL,
)
last_seen = get_last_seen()  # ISO date or None
```

If `last_seen is None`, this is the first run. Seed state without alerting:
fetch the index, advance the watermark to today, emit no report section.

### Phase 1: Fetch the index

Use the `web_fetch` tool on `BLOG_URL`. Do NOT use raw `httpx`/`urllib`/`curl`
on `claude.com` from inside a utility — the WAF returns 403 to container
egress regardless of User-Agent (verified 2026-05-14). The tool path
gets through.

```python
content = web_fetch(BLOG_URL)        # however your harness exposes the tool
posts = parse_claude_blog(content)   # ~16 most-recent posts, newest-first
```

### Phase 2: Filter + decide

```python
new = filter_new(posts, last_seen)   # posts strictly newer than last_seen
```

- `new` empty → no report section. Still advance the watermark
  (`set_last_seen(posts[0]['date'])`) so we don't re-scan history every day.
- `new` non-empty → continue to Phase 3.

### Phase 3: Enrich each new post with a one-sentence summary

For each post in `new`, deep-fetch the post URL with a small token budget
(~500 tokens). Read the lede and condense to ONE factual sentence — what's
new, what's the change, what's the announcement. No editorializing, no
"exciting", no "important". Oskar reads the link if he wants depth.

Examples of good one-liners:
- "Adds AWS as a deployment surface alongside Vertex AI and Microsoft Foundry."
- "Image-scaling guidance: downscale to 1280×720 (4.6 family) or 1080p (Opus 4.7) before sending."
- "Public beta opens; previously customer-listed only."

### Phase 4: Emit the report section

Append to the calendar-event description HTML (after Sleep, before Zeitgeist
or wherever it fits the day's flow):

```html
<h2>Anthropic news</h2>
<ul>
  <li><a href="URL">Title</a> <em>(Category)</em> — one-sentence summary.</li>
  ...
</ul>
```

The `format_for_report(new)` helper produces the `<li>` rows with placeholder
"— DATE" trailing text; replace each "— DATE" with your one-sentence summary
before emitting.

Also add each post URL to the existing `<h2>Sources</h2>` list at the end of
the report (per the Daily Perch routine's existing Sources convention).

### Phase 5: Commit state + store audit memory

```python
if posts:
    set_last_seen(posts[0]["date"])

from scripts import remember
from datetime import date as _date
today_iso = _date.today().isoformat()
remember(
    f"anthropic-news check {today_iso}: {len(new)} new post(s) since "
    f"last_seen={last_seen}; watermark now {posts[0]['date'] if posts else last_seen}. "
    f"Posts: " + ("; ".join(f"{p['date']} {p['title']}" for p in new) if new else "none"),
    type="experience",
    tags=["perch-time", "session-log", "anthropic-news", "claude-blog", today_iso],
)
```

The calendar event is the alert (ephemeral); this memory is the durable
record for delta-checking the next run.

### Known limitations (v1)

- The parser anchors on `/blog/<slug>` links and looks back ~600 chars for
  the nearest date. Categories are matched against a hardcoded set
  (`_CATEGORIES` in `news_watch.py`) and can occasionally bleed from a
  neighboring card when a post itself has no category. The title + URL +
  date are reliable; category is decorative.
- If claude.com publishes a feed URL (atom/rss), prefer it. As of
  2026-05-14, no feed was discoverable from container egress (WAF blocks
  raw HTTP regardless of UA). Probe periodically: try web_fetch on
  `/blog/feed.xml`, `/blog/atom.xml`, `/blog/rss.xml` and grep raw HTML
  of `/blog` for `<link rel="alternate">`.
