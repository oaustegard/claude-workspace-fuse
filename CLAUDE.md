# CLAUDE.md — muninn-utilities

Source-of-truth for everything Muninn-specific that runs in a session. Two
subsystems: `remembering/` (memory skill, Turso-backed FTS5 + vector + tags)
and `muninn_utils/` (Python package of session utilities materialized into
`~/muninn_utils/` at boot). Both used to live in `claude-skills` or as Turso
`utility-code` memories; this is their dedicated home.

## Context Roadmap

```
remembering/              Memory subsystem — skill-shaped for backward compat
  SKILL.md                Skill description (mounted under /mnt/skills/user/remembering/)
  scripts/                Core: boot.py, memory.py, turso.py, config.py, hints.py,
                            capabilities.py (trigger-first boot routing),
                            task.py, spokes.py, result.py, audit.py, state.py, utilities.py
  references/             Field reference, recall vocabulary, remembering-api docs
  tests/                  Hardening tests (mocked Turso + GitHub — no live creds needed)
  CHANGELOG.md            Version history; bump here before tagging a release
muninn_utils/             Python package — materialized to ~/muninn_utils/ at boot
  __init__.py
  blog_publish.py         Full blog post publish + Bluesky announce
  bsky_card.py            Bluesky card/post creation
  bsky_limit.py           300-grapheme cap check for bsky posts
  correction_gate.py      Held-in/held-out regression gate for boot-loaded self-corrections (#83)
  issue_close.py          GitHub issue close with memory
  memory_tfidf.py         TF-IDF over memory corpus
  news_watch.py           News monitoring utilities
  perch_publish.py        Perch flight log publish
  perch_triage.py         Perch triage workflow
  remind.py               Reminder/nag memory creation
  satisfaction_skew.py    Measure failure:success storage skew — correction vs satisfaction-analog ratio, trend, shapes (#85)
  task_policy.py          Task routing policy
  verify_patch.py         Patch verification utilities
  whtwnd.py               WhiteWind (AT-proto blog) posting
  zeitgeist_delta.py      Zeitgeist delta computation
  use_when.json           Routing hints for utility selection
  tests/                  muninn_utils unit tests
manifests/                Install manifests — one JSON per utility
scripts/
  build-tools-index.py    Tooling index builder
README.md                 Layout + migration history (read this for full context)
```

## Context Understanding

Boot sequence (both CCotw and Claude.ai):
1. `muninn-utilities` tarball fetched fresh
2. `remembering/` overlaid onto `/mnt/skills/user/remembering/`
3. `muninn_utils/*.py` materialized into `~/muninn_utils/`
4. `boot()` called from `remembering/scripts/boot.py` — loads identity,
   profile, ops, and recent memories from Turso
5. `claude-skills` tarball fetched for general skills

The `remembering/` mirror in `claude-skills` is auto-synced FROM this repo via
a scheduled workflow in claude-skills. It is deprecated — kept for marketplace
continuity, not for new development.

`flowing` is NOT in muninn_utils. It's a thin re-export wrapper over
`/mnt/skills/user/flowing/` (from claude-skills). It resolves at runtime from
the mount, not from this package.

## Domain Constants

| | |
|---|---|
| remembering boot script | `remembering/scripts/boot.py` |
| Turso credentials | `TURSO_TOKEN`, `TURSO_DB_URL` from env |
| muninn_utils materialized path | `~/muninn_utils/` |
| remembering skill path | `/mnt/skills/user/remembering/` |
| Manifests | `manifests/<utility-name>.json` (one per util) |
| Claude.ai boot fetcher | `oaustegard/claude-skills#625` (in remembering) |
| CCotw boot fetcher | `oaustegard/claude-workspace#55` |
| Release tag format | `vX.Y.Z` (bump `remembering/CHANGELOG.md` first) |

## Parsing Schema

- **Utility manifest** (`manifests/<name>.json`): describes when to use the
  utility, its parameters, and env requirements. The `indirect: true` env
  field flags vars accessed transitively (skip drift check for those).
- **`use_when.json`**: routing hints for utility selection — which utility
  handles which task shape.
- **`remembering/references/`**: field reference for recall(), remember(), and
  config_get(). The authoritative API docs.
- **Release**: bump `remembering/CHANGELOG.md`, then `git tag vX.Y.Z` + push.
  The sync workflow picks up the tag and mirrors to claude-skills.

## Error Patterns

**Do not edit `remembering/` in `claude-skills`.** It is a deprecated mirror
that the sync workflow overwrites. All changes go in this repo.

**Turso 503 on cold start is expected — not a credentials error.** The proxy
retries with backoff. See ops entry `proxy-503-retry-pattern` for the correct
pattern. Symptom: first call fails with 503, subsequent calls succeed.

**`flowing` imports fail if `/mnt/skills/user/flowing/` is not mounted.** This
is by design — `flowing` is not in muninn_utils. It resolves from the
claude-skills mount. In CI (no mount), mock the flowing calls.

**Tests need the mount for flowing.** `muninn_utils/tests/` resolve flowing
from `/mnt/skills/user/flowing`. Tests will fail in environments without
claude-skills mounted unless those imports are mocked.

**`remembering/tests/` are safe to run anywhere.** They use mocked Turso and
GitHub I/O — no live credentials required.

**Utility not yet migrated?** Check for Turso `utility-code` memories as
fallback. `boot()` materializes non-migrated utilities from there. Once
migrated, the Turso entry becomes stale and the file in `muninn_utils/` takes
precedence.

## Reusable Results

- **Adding a utility**: add `muninn_utils/<name>.py`, `manifests/<name>.json`,
  update `muninn_utils/__init__.py`, run tests.
- **Tests**: `python3 -m pytest muninn_utils/tests/` and
  `python3 remembering/tests/test_hardening.py`
- **Migration history**: memory `0d63ed4f`; `README.md` background section;
  PR #4 (install_utilities retirement) and PR #10 (manifest audit cleanup).
- **Manifest audit result**: memory `16326150` (PR #10, 2026-05-10) —
  17 warnings → 1; `indirect: true` env field added to schema.
- **remembering API**: `config_get('remembering-api')` — full field reference
  for recall(), remember(), config_get(), config_set().
