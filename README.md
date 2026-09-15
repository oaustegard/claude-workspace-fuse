# muninn-utilities

Source-of-truth for everything Muninn-flavored that runs in a session:

- `remembering/` — Muninn's memory subsystem (Turso-backed, FTS5, decision traces, autonomous curation). Skill-shaped (`SKILL.md`, `scripts/`, `references/`, `tests/`) so it can still be mounted under `/mnt/skills/user/remembering/` for backward compatibility.
- `muninn_utils/` — Python package of utilities that boot materializes into `~/muninn_utils/`. Originally migrated from Turso `utility-code` memories per memory `0d63ed4f`, and grown well past that batch since.
- `snapshot/` — builds a static, personal-scope-filtered snapshot of Muninn as a distributable claude-skill.
- `okf/` — exports a slice of memory as an Open Knowledge Format bundle another agent can read with `cat`.

The first two used to live elsewhere — `remembering/` in
[`oaustegard/claude-skills`](https://github.com/oaustegard/claude-skills) as a
generic skill, `muninn_utils/*` as Turso `utility-code` memories materialized
at boot. Both became Muninn-specific in practice. This is their dedicated
home.

## Layout

```
muninn-utilities/
├── CLAUDE.md               # Context roadmap — read first when working in here
├── remembering/            # Memory subsystem (skill-shaped)
│   ├── SKILL.md
│   ├── scripts/            # boot, memory, turso, config, capabilities, task, gen_manifest, …
│   │   ├── defaults/       # Runtime JSON loaded by path, not imported
│   │   └── tasks/          # Routine definitions (fly, sleep, zeitgeist, …)
│   ├── references/
│   ├── tests/
│   ├── MANIFEST.txt        # File list for the raw.githubusercontent transport
│   └── CHANGELOG.md
├── muninn_utils/           # Importable Python package
│   ├── use_when.json       # Routing hint per module — the live catalog
│   └── tests/
├── muninn-boot/            # The boot skill: SKILL.md + scripts/boot.sh
├── manifests/              # One install manifest per utility (JSON + REVOKE.md)
├── snapshot/               # Muninn-as-a-skill builder
├── okf/                    # Open Knowledge Format export + lint
├── docs/                   # getting-started, reference, overall-structure, mcp-migration
├── scripts/build-tools-index.py
└── .well-known/install-manifests.json
```

The `muninn_utils` module list is deliberately not enumerated here. It changes
most weeks, and a hand-maintained copy of it is what went stale in the previous
version of this file. `muninn_utils/use_when.json` carries one routing line per
module and is what boot renders; `CLAUDE.md` carries the same list with one-line
descriptions.

## What boot.sh does, in order

`muninn-boot/scripts/boot.sh` runs as the first action of every Muninn
conversation, in this order:

1. **Source env** from `$MUNINN_PROJECT_DIR` (default `/mnt/project`) with
   `set -a`, so values overwrite rather than merge. First, because the tarball
   transport needs `GH_TOKEN`.
2. **Sideload muninn-utilities** → `/home/claude/muninn-utilities`.
3. **Sideload claude-skills** → `/mnt/skills/user` (general skills: `flowing`,
   `browsing-bluesky`, `declauding`, …).
4. **Write the `.pth`** at a site-packages directory resolved at runtime —
   `python3.12/dist-packages` on Claude.ai, `python3.11/site-packages` in
   Cowork.
5. **Run `boot()`** from `remembering/scripts/boot.py`: identity, profile, ops,
   recent memories, task routing, capability catalog.
6. **Touch the sentinel** last, only on success. A warm container fast-exits in
   ~0s, so re-running boot is cheap and idempotent.

Each sideload has three transports, tried in order: the codeload tarball (one
request, where codeload is not intercepted), `gh-api-proxy`'s `/tarball` (one
request, follows the 302 server-side so the session never touches a blocked
host), and `raw.githubusercontent.com` plus `MANIFEST.txt` (one request per
file, needs no credentials at all).

`raw` is CDN-cached on branch refs for minutes and the cache is not
client-bustable, so a tier-3 boot shortly after a push silently loads pre-push
code. Pin `MUNINN_UTILS_REF=<sha>` when iterating.

Both [`oaustegard/claude-workspace`](https://github.com/oaustegard/claude-workspace)
(Claude Code on the Web) and the Claude.ai project instructions point here.

## GitHub transport (`muninn_utils/gh_proxy.py`)

Anthropic's session egress proxy intercepts `codeload.github.com`,
`api.github.com`, and `github.com` and returns 403. Session types with an
`add_repo` tool can grant themselves in-scope access; **Cowork and the scheduled
task runner have no such tool**, so every GitHub call fails there.

`gh_proxy` tries the direct path first and falls back to
[`gh-api-proxy`](https://gh-api-proxy.austegard.workers.dev) on the interception
signature, then latches. No session-type detection, no config flag.

```python
from muninn_utils.gh_proxy import graphql, rest, commit_files, open_pr

data = graphql('{ viewer { login } }')          # yes, GraphQL works
status, repo = rest('/repos/oaustegard/muninns-inbox')
commit_files(REPO, 'my/branch', {'a.py': '...'}, 'message')
```

Three things this encodes that cost four weeks to learn:

1. **There are two interception messages, not one.** The repo-scope 403 says
   "Use `add_repo`"; the GraphQL 403 says "only the pinned set of PR-review
   operations is served" and never mentions `add_repo`. A detector keyed on
   `add_repo` silently fails to fall back — which is why the muninns-inbox
   GraphQL block survived 28 routine runs. Both bodies carry a
   `docs.anthropic.com` `documentation_url`; that is the reliable tell.
2. **`GH_TOKEN` is preset to `proxy-injected` in the container.** It is truthy,
   so any `os.environ.get("GH_TOKEN")` presence check passes while the token is
   meaningless to GitHub. The failure surfaces much later as an inscrutable 401
   "Bad credentials". Use `gh_proxy.valid_token()`; source env with overwrite,
   never `setdefault`.
3. **Writes go through the Git Data API**, not the Contents API — the latter is
   write-blocked through the session proxy even with `add_repo` push access.

## Sideload manifest (`remembering/MANIFEST.txt`)

`raw.githubusercontent.com` is *not* intercepted, so it is the fallback transport
when codeload is blocked. But raw has no directory listing, and deriving the file
list by walking `from .x import` statements misses every runtime **data** file
(`scripts/defaults/*.json`, `scripts/tasks/*.md`). Symptom: boot succeeds but the
Task Routing block silently renders empty.

`MANIFEST.txt` is that list, and it covers `muninn_utils/` as well as
`remembering/`. A runtime file missing from it is invisible to a tier-3 boot:
present on Claude.ai, absent in Cowork, with no error in either place. Regenerate
after adding or removing one:

```bash
python3 remembering/scripts/gen_manifest.py           # from a checkout
python3 remembering/scripts/gen_manifest.py --check   # exit 1 if stale
```

No workflow in this repo runs `--check`. It is a pre-push step, and the only
actor that runs it is whoever added the file.

## Install manifests (`manifests/`)

One directory per utility, holding a versioned JSON manifest (scopes, actions,
smoke test, kill switch) and a `REVOKE.md`. `boot()` audits them and warns on
stderr about a manifest with no module, a module with neither manifest nor
`use_when` entry, and required env that is unconfigured.

`.github/workflows/notify-tools-index.yml` fires a `repository_dispatch` at
`muninn.austegard.com` when `manifests/` changes, so the site rebuilds
`.well-known/tools.json` promptly rather than waiting for its daily schedule.

## Relationship to claude-skills

There is no longer a mirror. `remembering/` was vendored into
`oaustegard/claude-skills` behind a scheduled sync workflow; the workflow was
removed on 2026-05-10 (claude-skills#639) and the leftover stub directory on
2026-07-07. This repo is the only home, so edit `remembering/` here.

What remains is the reverse direction: boot sideloads claude-skills into
`/mnt/skills/user` for the general, non-Muninn-specific skills.

## Tests

```
python3 -m pytest muninn_utils/tests/
python3 -m pytest remembering/tests/
```

`muninn_utils` tests resolve `flowing` from `/mnt/skills/user/flowing` (or a
sibling claude-skills clone). `remembering` tests use mocks for Turso and
GitHub I/O — no live credentials required.

Lint what a branch added rather than the whole tree, which carries a large
pre-existing baseline:

```
python3 -m muninn_utils.ruff_gate --base main
```

## Docs

- [`docs/getting-started.md`](docs/getting-started.md) — build the minimal
  `remember` → `recall` → `supersede` loop over Turso. Start here.
- [`docs/reference.md`](docs/reference.md) — API surface of the memory layer and
  the snapshot builder.
- [`docs/overall-structure.md`](docs/overall-structure.md) — who the docs are
  for and how they are organized.
- [`docs/mcp-migration.md`](docs/mcp-migration.md) — moving the backend to a
  deployed Worker ([`oaustegard/muninn-mcp`](https://github.com/oaustegard/muninn-mcp)).
- [`CLAUDE.md`](CLAUDE.md) — context roadmap for an agent working in this repo.

## Background

- [memory `0d63ed4f`](https://github.com/oaustegard/claude-skills) — migration tracker
- [`oaustegard/muninn.austegard.com#124`](https://github.com/oaustegard/muninn.austegard.com/pull/124) — first batch of utilities (initially landed in mac, since moved here)
- [`oaustegard/muninn.austegard.com#125`](https://github.com/oaustegard/muninn.austegard.com/pull/125) — removed `muninn_utils/` from mac
- [`oaustegard/claude-workspace#55`](https://github.com/oaustegard/claude-workspace/pull/55) — CCotw boot fetcher
- [`oaustegard/claude-skills#625`](https://github.com/oaustegard/claude-skills/pull/625) — Claude.ai boot fetcher (in `remembering`)
- [`oaustegard/claude-skills#639`](https://github.com/oaustegard/claude-skills/pull/639) — stopped vendoring `remembering` into claude-skills
