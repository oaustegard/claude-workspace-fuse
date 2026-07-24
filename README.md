# muninn-utilities

Source-of-truth for everything Muninn-flavored that runs in a session:

- `remembering/` — Muninn's memory subsystem (Turso-backed, FTS5, decision traces, autonomous curation). Skill-shaped (`SKILL.md`, `scripts/`, `references/`, `tests/`) so it can still be mounted under `/mnt/skills/user/remembering/` for backward compatibility.
- `muninn_utils/` — Python package of utilities that boot materializes into `~/muninn_utils/`. Migrated from Turso `utility-code` memories per memory `0d63ed4f`: `blog_publish`, `bsky_card`, `bsky_limit`, `issue_close`, `memory_tfidf`, `perch_publish`, `perch_triage`, `remind`, `verify_patch`, `whtwnd`, `zeitgeist_delta`.

Both used to live elsewhere — `remembering/` in
[`oaustegard/claude-skills`](https://github.com/oaustegard/claude-skills) as a
generic skill, `muninn_utils/*` as Turso `utility-code` memories materialized
at boot. Both became Muninn-specific in practice. This is their dedicated
home.

## Layout

```
muninn-utilities/
├── remembering/            # Memory subsystem (skill-shaped)
│   ├── SKILL.md
│   ├── scripts/            # boot, memory, turso, hints, tasks, …
│   ├── references/
│   └── tests/
├── muninn_utils/           # Importable Python package
│   ├── __init__.py
│   ├── blog_publish.py
│   ├── bsky_card.py
│   ├── bsky_limit.py
│   ├── issue_close.py
│   ├── memory_tfidf.py
│   ├── perch_publish.py
│   ├── perch_triage.py
│   ├── remind.py
│   ├── verify_patch.py
│   ├── whtwnd.py
│   ├── zeitgeist_delta.py
│   └── tests/
└── README.md
```

## How it gets to a session

A Muninn session bootstraps in this order:

1. **Container layer** restored (system packages, Python deps)
2. **muninn-utilities** tarball fetched first — `remembering/` and `muninn_utils/` both land on disk
3. **Boot** runs from `remembering` here (loads identity, profile, ops, recent memories from Turso; materializes any non-migrated `utility-code` memories as `~/muninn_utils/` fallback)
4. **claude-skills** tarball fetched for general skills (`flowing`, `browsing-bluesky`, `closing-issues`, etc.)

Both [`oaustegard/claude-workspace`](https://github.com/oaustegard/claude-workspace)
(Claude Code on the Web) and the Claude.ai project instructions point here.

## claude-skills mirror

`remembering/` is auto-mirrored to
[`oaustegard/claude-skills/remembering/`](https://github.com/oaustegard/claude-skills/tree/main/remembering)
via a scheduled workflow that lives in `claude-skills` itself
(`.github/workflows/sync-remembering-from-muninn-utilities.yml`). It pulls
the latest `remembering/` from this public repo and opens a PR in
claude-skills if anything changed.

The workflow is a same-repo write so it needs no extra secrets — the
default `GITHUB_TOKEN` is sufficient.

The mirror is **deprecated** — kept fresh for marketplace continuity, not
for new development. To change `remembering`, edit the files here.

## Tests

```
python3 -m pytest muninn_utils/tests/
python3 remembering/tests/test_hardening.py
```

`muninn_utils` tests resolve `flowing` from `/mnt/skills/user/flowing` (or a
sibling claude-skills clone). `remembering` tests use mocks for Turso and
GitHub I/O — no live credentials required.

## Background

- [memory `0d63ed4f`](https://github.com/oaustegard/claude-skills) — migration tracker
- [`oaustegard/muninn.austegard.com#124`](https://github.com/oaustegard/muninn.austegard.com/pull/124) — first batch of utilities (initially landed in mac, since moved here)
- [`oaustegard/muninn.austegard.com#125`](https://github.com/oaustegard/muninn.austegard.com/pull/125) — removed `muninn_utils/` from mac
- [`oaustegard/claude-workspace#55`](https://github.com/oaustegard/claude-workspace/pull/55) — CCotw boot fetcher
- [`oaustegard/claude-skills#625`](https://github.com/oaustegard/claude-skills/pull/625) — Claude.ai boot fetcher (in `remembering`)
