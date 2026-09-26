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
│   ├── MANIFEST.txt        # Legacy file list; boot.sh 2.0.0 clones instead
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

## What boot.sh does

`muninn-boot/scripts/boot.sh` (2.0.0) runs as the first action of every Muninn
conversation and does one thing: `git clone --depth 1` this repo to
`/home/claude/muninn-utilities` (codeload tarball as fallback where the session's
git proxy refuses github.com) and write a `.pth` so `muninn_utils`,
`remembering` and every skill's `scripts/` import. `GitHub.env` is sourced if
present, transitionally, until GitHub write tools exist on the worker.

It sources no `Turso.env` and does not run `boot()`: the payload comes from the
Muninn MCP connector's `boot` tool, and memory reads and writes go through the
connector. It does not sideload claude-skills either; marketplace sync already
places them in the session. Pin `MUNINN_UTILS_REF=<sha>` to test an unmerged
state.

`remembering/scripts/boot.py` is what the worker ports; it still runs from a
checkout with Turso credentials in the environment.

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

## Sideload manifest (`remembering/MANIFEST.txt`) — legacy

Not read by boot.sh 2.0.0, which clones. Kept for any raw.githubusercontent
consumer that still needs a file list; regenerate with
`python3 remembering/scripts/gen_manifest.py` if you touch it.

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
