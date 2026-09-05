# Revoking muninn-news-watch

This tool stores a single watermark (an ISO date) in the Muninn Turso DB
config table; it does not store any content from claude.com, nor does it
fetch any URLs directly (fetching is delegated to the caller's `web_fetch`).
Revocation is credential rotation plus optional watermark cleanup.

## Step 1 — Stop future writes (credential rotation)

Rotate `TURSO_TOKEN` at https://app.turso.tech/. This immediately stops the
tool from advancing or reading the watermark. **Primary kill.**

`TURSO_TOKEN` is shared across all memory-touching utilities (`remembering`,
`remind`, `issue_close`, `memory_tfidf`, `task_policy`, etc.). Generate a
new token and update consumers before revoking the old.

## Step 2 — Remove the watermark (optional)

The watermark is a single config row keyed `claude-blog-last-seen-iso` under
category `ops`. To clear it:

```python
from scripts import config_set
config_set('claude-blog-last-seen-iso', '', 'ops')
```

After clearing, the next call to `get_last_seen()` returns `None` and the
following `parse_claude_blog` + `filter_new` run treats itself as a first
run (no posts reported until the watermark is re-seeded by `set_last_seen`).

## Step 3 — Uninstall the code

If installed via the manifest's `runtime.install` (in v0.4 the install is
`preinstalled`, so this means removing it from the muninn-utilities tarball
build), delete the module file `muninn_utils/news_watch.py` and the
manifests at `manifests/news-watch/`.

## What this kill switch cannot do

- Cannot retract perch reports that have already surfaced new posts in past
  sessions — those live in the report HTML the caller emitted.
- Cannot affect claude.com itself; the tool only reads its blog page through
  the caller's web_fetch and stores a single date locally.
