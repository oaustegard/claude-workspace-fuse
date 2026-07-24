# Reference

API surface of muninn-utilities, scoped for the borrower and maintainer: the
reusable `remembering` memory layer and `snapshot` builder get full entries; the
thirteen `muninn_utils` task utilities are listed as a catalog, since they are
Muninn-specific applications of the same pattern rather than core API.

In Muninn's environment the memory layer is imported as `from scripts import …`.
`scripts` is the package name for `remembering/scripts/`.

## remembering — the memory layer

### memory

Core store: write, read, revise, and maintain memories over Turso.

- `remember(summary, type=None, *, tags=None, conf=None, refs=None, priority=0, valid_from=None, sync=True, session_id=None, alternatives=None, entities=None, importance=None)` — Store a memory. `type` is required. Returns the new memory id.
- `recall(search=None, *, query=None, n=10, tags=None, type=None, tag_mode='any', strict=False, since=None, until=None, tags_all=None, tags_any=None, raw=False, fetch_all=False, …)` — Query memories by full-text `query`, `tags`, `type`, and time bounds. Returns an iterable result set.
- `recall_since(after, *, search=None, query=None, n=50, type=None, tags=None, tag_mode='any', raw=False)` — Recall memories created after a timestamp.
- `recall_between(after, before, *, search=None, query=None, n=100, type=None, tags=None, tag_mode='any', raw=False)` — Recall memories within a time range.
- `recall_batch(queries, *, n=10, type=None, tags=None, tag_mode='any', raw=False)` — Run several searches in one HTTP round-trip.
- `supersede(original_id, summary, type, *, tags=None, conf=None, priority=None, drift_class=None)` — Record a correction as a new memory that replaces `original_id`. `type` required. Returns the new id.
- `forget(memory_id)` — Soft-delete a memory so it stops surfacing in recall. Accepts full or partial UUIDs. Recoverable.
- `strengthen(memory_id, boost=1)` / `weaken(memory_id, drop=1)` — Raise or lower a memory's priority, changing how early it surfaces.
- `get_chain(memory_id, depth=3)` — Follow supersession and reference links to reconstruct the context graph around a memory.
- `get_alternatives(memory_id)` — Read the alternatives recorded on a decision memory.
- `consolidate(*, tags=None, min_cluster=3, dry_run=True, session_id=None)` — Fold clusters of related memories into summary memories. Defaults to a dry run.
- `curate(*, dry_run=True, consolidation_threshold=3, stale_days=90, low_priority_cap=-1, max_actions=20)` — Detect duplicates, stale, and consolidation candidates in one pass. Defaults to a dry run.
- `prune_by_age(...)` / `prune_by_priority(...)` — Drop memories past an age or below a priority floor.

### config

Operating instructions stored as queryable data, separate from memories.

- `config_get(key)` — Get a config value by key.
- `config_set(key, value, category, *, char_limit=None, read_only=False, boot_load=None)` — Set a config value with optional constraints. `boot_load=True` loads it at session start; new entries default to reference-only (`boot_load=0`) — boot-load is opt-in and should be a compact trigger pointing at the payload, not the payload itself.
- `set_rule(key, value, category, *, drift_class, rationale=None, char_limit=None, read_only=False, boot_load=None)` — Set a profile or ops rule with a mandatory `drift_class` recording how it changed.
- `config_list(category=None)` — List config entries, optionally filtered by category.
- `config_delete(key)` — Delete a config entry.

### boot

Session lifecycle: reconstruct working context in a fresh process.

- `boot(mode=None, task=None, telemetry=False)` — Load profile and ops from Turso, surface reminders and open tasks. The cold-start entry point.
- `journal(topics=None, user_stated=None, my_intent=None)` — Record a journal entry. Returns the entry key.
- `sessions(n=10, *, include_counts=False)` — List recent session checkpoints.

### task

Structural discipline for multi-step work.

- `task(name, steps=None, task_type=None, require_store=True, persist=True)` — Create a tracked task with a type-specific checklist.
- `task_resume(name)` — Reload a persisted task by name for cross-session continuity.
- `recall_gate(topic, require_results=True)` — Context manager that forces a `recall()` before analysis proceeds.

### spokes

Registry of the repositories the agent maintains.

- `spokes_list()` — Return registered spokes from config. No GitHub calls.
- `spokes_status(repos=None)` — Fetch live GitHub state for registered spokes.
- `spokes_discover(owner='oaustegard')` — List an owner's repos, flagging which are registered.

### hints

- `recall_hints(context=None, *, terms=None, include_tags=True, include_summaries=True, min_matches=1)` — Surface memories relevant to a context string or term list, for proactive grounding.

## snapshot — distributing memory as a skill

A pipeline that turns a live memory store into a portable claude-skill. Run in
order:

- `pull` — Pull config and memories from the live database.
- `filter` — Retain and redact memory bodies for distribution.
- `cluster` — Group memories into knowledge-base files by primary tag.
- `kb` — Write the knowledge-base cluster files.
- `compose_instruction` / `compose_bridge` — Compose `SKILL.md` and its bridge table.
- `build` — Assemble the snapshot as a claude-skill.

## muninn_utils — example applications (catalog)

Thirteen task utilities, each a flowing-graph orchestrator wrapping one Muninn
workflow. They are instances of the pattern, not core API; a borrower reads them
as examples. See the flowing Diving Deeper topic for one worked through in full.

| Utility | Purpose |
|---|---|
| `blog_publish` | Publish a blog post: validate HTML, push the page, update the Atom feed, announce. |
| `bsky_card` | Compose a Bluesky post with a link card, facets, and uploaded blob. Includes `like`/`unlike`. |
| `bsky_limit` | Measure and truncate text against Bluesky's 300-grapheme limit (grapheme-aware). |
| `issue_close` | Close a GitHub issue with a learning synthesis. |
| `memory_tfidf` | TF-IDF similarity index over memories. |
| `news_watch` | Watch the Claude blog for new posts during the daily routine. |
| `perch_publish` | Publish perch flight logs to the website. |
| `perch_triage` | Triage open flight logs via GitHub discussion reactions. |
| `remind` | Reminders with due dates, recurrence, snooze, and a boot-surfaced nag mode. |
| `task_policy` | Load and schedule autonomous perch tasks. |
| `verify_patch` | Semi-formal patch verification with outcome tracking. |
| `whtwnd` | Publish to a WhiteWind blog over ATProto. |
| `zeitgeist_delta` | Semantic delta check to deduplicate before storage. |
