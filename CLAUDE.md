# Claude Workspace (FUSE variant)

This repo is a **fork of `oaustegard/claude-workspace`** that adds a
read-only FUSE filesystem mounted at `/mnt/muninn/`, projecting the
active Turso memory corpus as individual markdown files.

The point: bulk operations on memories — `grep -lr 'fuse' /mnt/muninn/memories/`,
`wc -l /mnt/muninn/memories/*.md`, Read on a single memory file — work
through native Unix tools without writing custom Python. See
`docs/memfs.md` for design notes and `scripts/muninn_memfs.py` for the
implementation (~250 lines).

Everything below is inherited from the parent hub. The only deltas are:
- `scripts/muninn_memfs.py` (the FUSE server)
- `scripts/install-{mojo,pytorch,pysr}.sh` (on-demand heavy-dep installers; pytorch is a fallback since `torch-cpu` is in the default layer composition)
- `tests/test_muninn_memfs.py` (26 unit tests, no FUSE/Turso needed)
- `boot-ccotw.sh` (two extra functions: `_verify_fuse_deps` warning fallback, `_start_memfs_background` for the memfs mount)
- `layers/Containerfile.fuse` (adds `fusepy`; cached as `layer-fuse-<hash>`)
- `.claude/container-layers.json` (`["base", "scientific", "torch-cpu", "fuse"]` — parent default + fuse)
- `docs/memfs.md` (design notes)

## Reach for /mnt/muninn first

The FUSE mount projects 1490+ memories as individual markdown files. Before
WebSearch, before `recall()` over HTTP, before answering from training-data
recall — if the task involves "what do we know about X", "have we done Y
before", or "is there prior art on Z", grep the mount:

```bash
grep -l 'X' /mnt/muninn/memories/*.md       # ~200ms across the whole corpus
grep -lE 'pattern1|pattern2' /mnt/muninn/memories/*.md
```

Diagnosed miss (session 854f6b7c, 2026-05-17): wrote a tree-sitter grammar
without checking the mount first; would have surfaced
`77cf6b41-tree-sitter-setup-gotcha`, `e2de0a20-tree-sitter-language-pack-163-latest`,
`fb27a55a-pr-536-treesitpy-cli-cross-process-cache` — three memories directly
relevant to the scanner.cc-doesn't-link discovery that got re-done from scratch.

The mount is read-only by design; for writes still use `remember()` from the
remembering skill (HTTP path to Turso).

## Heavy deps on demand (opt-in cached layers)

The composition in `.claude/container-layers.json` is the always-on slate
(`base`, `scientific`, `torch-cpu`, `fuse`). Heavier optional layers stay
out of the default and restore on demand. Each one is its own cached layer
(`layer-<name>-<hash>`); add it to the manifest to always-on it, or invoke
the installer when a session needs it ad-hoc:

| Tool | Trigger | Restore command | Cache hit | Cache miss (build + push) |
|---|---|---|---|---|
| Mojo | Any `.mojo` file, `mojo` CLI, fusemojo/tree-sitter-mojo work | `scripts/install-mojo.sh` | ~30s download+extract | ~3 min one-time, then cached for everyone |
| PyTorch (fallback) | `import torch` when `torch-cpu` was dropped from the manifest | `scripts/install-pytorch.sh` | ~20s | ~2 min one-time |
| PySR | `import pysr`, eml-sr spoke, SymbolicRegression.jl | `scripts/install-pysr.sh` | ~30s (incl. precompiled `/root/.julia`) | ~5 min one-time |

Each installer is idempotent — returns instantly when the tool is already
present. Run it *before* the first command that needs the tool; don't wait
for `import` to fail.

The cache lives in [oaustegard/claude-container-layers](https://github.com/oaustegard/claude-container-layers)
as GitHub Releases (one per `layer-<name>-<hash>`). First invocation of a
given layer pays the build cost and pushes the tarball; every subsequent
invocation (anyone, any session) is a cache hit.

**Always-on (default composition, always cached):**
- `base` — httpx, libsql-experimental, gh CLI, env-source shim
- `scientific` — scipy, scikit-learn, pandas, tree-sitter-language-pack
- `torch-cpu` — PyTorch CPU-only build
- `fuse` — `fusepy` Python bindings (libfuse2 + fusermount are already in the base container image)

**Why not fresh `pip install`?** Network round-trips + dependency resolution
+ wheel-by-wheel installation = minutes even when the bytes are small.
Tarball restore is a single stream, no Python-level activity, no resolver.
Especially worth it for PySR where the precompiled `/root/.julia` (~1GB)
would otherwise cost 5 minutes to rebuild on every fresh container.

This repo configures Claude Code on the Web to boot as **Muninn**.

## What happens on session start

The `SessionStart` hook in `.claude/settings.json` runs `boot-ccotw.sh`, which:
1. Bootstraps the container-layer skill from `oaustegard/claude-skills`
2. Reads `.claude/container-layers.json` and **composes** the listed layers (`base`, `scientific`, `torch-cpu`, `fuse` by default) via `scripts/compose_layers.py apply`. Each layer is cached independently in GitHub Releases as `layer-<name>-<hash>`, so changing one layer doesn't invalidate the others. Falls back to legacy single-`Containerfile` mode if no manifest exists.
3. Fetches skills fresh from `oaustegard/claude-skills` via tarball (always current, never cached in the container layer)
4. Tarballs `oaustegard/muninn-utilities` and overlays `remembering/` into `/mnt/skills/user/remembering/` (replacing the deprecated mirror that claude-skills still ships) and `muninn_utils/*.py` into `~/muninn_utils/`. Public repo — no `GH_TOKEN` required.
5. Sets up Python paths for the remembering skill (now sourced from muninn-utilities)
6. Verifies FUSE deps (`fusermount`, `import fuse`) — warns if missing because the `fuse` layer cache hasn't warmed yet for this session
7. Starts `scripts/muninn_memfs.py` in the background, mounting the Turso memory corpus at `/mnt/muninn/`
8. Outputs `<available_skills>` XML frontmatter into the context window
9. Runs `post-boot.sh`, which calls `boot()` from the muninn-utilities-installed remembering — loads the Muninn identity, profile, ops, and recent memories from Turso

Three deliberately separated layers:
- **Container layer** (cached): slow-to-install system packages, CLI tools, Python libs
- **Skills** (fresh every session): fetched from `claude-skills`, never stale
- **muninn-utilities** (fresh every session): fetched from `muninn-utilities`, source-of-truth for everything Muninn (`remembering/` + `muninn_utils/`)

## Boot recovery (cold-start scope lockdown)

Every boot step above that fetches a **spoke** (`claude-skills`,
`muninn-utilities`, `claude-container-layers`) goes through `codeload.github.com`.
The CCotw agent proxy scopes GitHub access per session: on a **cold start** the
spokes are out of scope, so every spoke `codeload` fetch returns **403** and boot
comes up degraded — no container-layer skill, no fresh skills, no `remembering`,
no `/mnt/muninn` mount, no identity. (Diagnosed repeatedly 2026-07-06; see
memories `74901b87`, `900d382b`, `8d31c188` for the three-tier proxy-scope model.)

The **only** in-session lever that widens scope is `add_repo`
(`mcp__Claude_Code_Remote__add_repo`). It is a **model tool** — it fires on a
turn. The `SessionStart` hook is a **shell script that runs before any turn
exists**, so it *cannot* call `add_repo`. This is a hard chicken-and-egg: no
edit to `boot-ccotw.sh` can pre-authorize the spokes.

The workaround moves the scope-widening to the first turn, where the model can
act:

1. `boot-ccotw.sh` no longer `exit 1`s when the container-layer skill fetch
   403s — it warns and continues, so warm-resume containers (where a prior
   session's `add_repo` scope persisted) still finish, and cold starts still
   write their health signals.
2. `scripts/ensure-scope.sh` (a `UserPromptSubmit` hook) checks boot health
   (`/mnt/muninn` mounted **and** `remembering` present). If degraded, it
   injects a `<boot-recovery-directive>` telling the model to `add_repo` the
   three spokes and invoke the **`muninn-boot`** skill. Silent on a healthy
   session.
3. The **`muninn-boot`** skill (`.claude/skills/muninn-boot/`, committed to this
   hub so it's discoverable on turn 1 with no fetch) is the model-invocable boot
   entrypoint. Its `scripts/boot.sh` is a thin, health-aware wrapper: a no-op
   when already healthy, otherwise it runs `scripts/session-recover.sh`, which
   confirms scope landed, re-runs boot idempotently, and guarantees the memfs
   mount via a `libfuse2`/`fuse`/`fusepy` apt+pip fallback for a cold fuse-layer
   cache. `_link_project_skills` in `boot-ccotw.sh` symlinks it into
   `~/.claude/skills` (registers next session, same one-session lag as the other
   slash skills).

**Hybrid, not either/or.** The `SessionStart` hook still runs `boot-ccotw.sh`,
so **warm resumes auto-boot** with zero model effort (scope persists across
container resumes). The `muninn-boot` skill carries **cold starts**, where the
model must `add_repo` first. One boot implementation (`boot-ccotw.sh`), two
callers (the hook for warm, the skill for cold).

**Obey the `<boot-recovery-directive>` first thing on any turn it appears** —
`add_repo` the three spokes, invoke `muninn-boot`, one line to Oskar that boot
self-healed, then proceed with his request.

**Call `add_repo` but NOT `register_repo_root`.** `add_repo` alone opens the
codeload/tarball channel — which is all boot needs. `register_repo_root` (and
the clone-then-register flow the `add_repo` response nudges toward) additionally
**inlines each spoke's `CLAUDE.md`, skills, and plugins** into context; add all
the spokes that way and their instructions pile up and cross-talk with this
hub's. The recovery deliberately skips it: scope without inlining. Empirically
confirmed — three `add_repo` calls with no `register_repo_root` gave working
codeload with zero spoke `CLAUDE.md` in context.

**On the durable-fix landscape (docs-checked 2026-07-07 against
[the CCotw docs](https://code.claude.com/docs/en/claude-code-on-the-web) +
[quickstart](https://code.claude.com/docs/en/web-quickstart)).** A CCotw
**environment** carries exactly four fields — name, network access, environment
variables, setup script. There is **no per-environment source-repo list**, so
the spokes cannot be attached at the *environment* level such that every new
session inherits them. That much of the "don't project the parent
`claude-workspace` model" caution (memory `74901b87`) holds — but the old
phrasing here, *"there is no environment editor,"* was **wrong**: the editor
exists, it just has no repo field. Memory `74901b87`'s own tier-(a) ("env
sources configured in the environment editor") mislocated the lever; its
self-correction two sentences later ("I misread `add_repo` resume-persistence as
env sources; he hadn't") was the accurate part.

What *does* exist is **session-level multi-repo selection**: the quickstart says
verbatim "You can add multiple repositories to work across them in one session,"
and a `claude.ai/code?repositories=<owner/repo,...>` prefill URL preselects
them. Repos chosen that way are cloned *before* the `SessionStart` hook runs, so
they would be in codeload scope from tick 0 — a real set-and-forget path if you
always launch from a bookmarked prefill URL carrying all four slugs.

**OPEN — needs one empirical test (flagged 2026-07-07).** Does session multi-repo
selection **inline each repo's `CLAUDE.md`** the way `register_repo_root` does?
The earlier claim here that the "add repository" feature "registers them fully /
inlines every `CLAUDE.md`" **conflated it with `register_repo_root` and was never
tested** — the only thing empirically confirmed (above) is that `add_repo`
*without* `register_repo_root` doesn't inline. The test is Oskar's to run:
launch one session via the 4-repo prefill URL, then observe (a) whether boot
self-heals with the recovery directive never firing, and (b) whether the spoke
`CLAUDE.md`s cross-talk in context. If (a) yes and (b) no → adopt the prefill URL
as the standing launcher and demote this recovery to warm-fallback. If (b) yes →
attach only the thin-`CLAUDE.md` spokes (`claude-container-layers` is a
near-empty cache store) and keep `add_repo` recovery for `claude-skills` /
`muninn-utilities`.

**Until that test returns, this first-turn recovery remains the standing
solution** — it grants exactly the codeload scope boot needs, on demand, without
inlining anything. `add_repo` scope also persists across container **resumes**
within a session, so warm resumes boot clean with no recovery needed (confirmed
again 2026-07-07). Note: the Cloudflare-Worker fallback (`scripts/cf-gh-proxy/`,
memory `8d31c188`) is **not present on this branch** — it never merged from
`claude/github-credentials-routine-failures-7llbhp`, so treat it as unbuilt if
the session-repo lever doesn't pan out.

## muninn-utilities is the home for everything Muninn

Per memory `0d63ed4f` and the architectural pivot of 2026-05:

- `remembering/` (memory subsystem) used to live in `claude-skills` as a "general" skill. In practice nobody but Muninn used it — Turso credentials, muninn.austegard.com endpoints, decision-trace conventions, identity-loading boot semantics are all hers. It's now sourced from muninn-utilities. claude-skills holds a deprecated mirror, kept fresh by a sync workflow on muninn-utilities for marketplace continuity.
- `muninn_utils/` (utility code: blog publish, bsky cards, issue close, etc.) used to live as Turso `utility-code` memories materialized to `~/muninn_utils/` by `install_utilities()`. Source-of-truth has moved to files in muninn-utilities.

Boot order matters: `claude-skills` is fetched first (provides general skills like `flowing`, `browsing-bluesky`, etc., AND the deprecated `remembering` mirror), then `muninn-utilities` overwrites `remembering/` with the canonical version. `boot()` then runs from the canonical source.

Turso `utility-code` memories remain as fallback for utilities not yet migrated. `install_utilities()` materializes everything from Turso, then the muninn-utilities fetch overwrites the migrated ones with their canonical files. Migration: 11 utilities now live in `muninn-utilities` — `blog_publish`, `bsky_card`, `bsky_limit`, `issue_close`, `memory_tfidf`, `perch_publish`, `perch_triage`, `remind`, `verify_patch`, `whtwnd`, `zeitgeist_delta` (last 8 added in [muninn-utilities#3](https://github.com/oaustegard/muninn-utilities/pull/3)). The `function_name` entry previously listed here was stale — no such Turso memory exists. `flowing` is tagged `utility-code` but is a thin re-export wrapper over `/mnt/skills/user/flowing/` and is intentionally left in Turso. Once the muninn-utilities copies are confirmed healthy across a few sessions, the corresponding Turso `utility-code` memories can be superseded.

## Identity

After boot, you ARE Muninn. The profile, personality, ops, and tensions
loaded by `boot()` define how you operate. Inhabit them — don't just
acknowledge them. If boot output appears in SessionStart context, treat
it as already loaded; do not re-run boot() unless it was absent.

## Verifying it worked

After boot, try:
```
python3 -c "import httpx; print(httpx.__version__)"
ls /mnt/skills/user/
```

## What happens on session stop

The `Stop` hook runs `persist-transcript.sh`, which:
1. Finds the current session's `.jsonl` transcript in `~/.claude/projects/`
2. Archives it to a GitHub Release on `oaustegard/claude-container-layers`
3. Also maintains a rolling `transcripts-latest` release with all transcripts
4. Requires `GH_TOKEN`; silently no-ops without it

## Credentials

For caching to work, create a `.env` file (gitignored) with:
```
GH_TOKEN=ghp_your_token_here
```

Without it, the layer still builds — it just can't cache/restore.

## Hub/Spoke Working Model

This repo (`claude-workspace`) is the **hub** — it boots and configures sessions.
Other repos are **spokes** that you work in during sessions. Key spokes:

- **`oaustegard/claude-skills`** — Skills fetched fresh at session start.
  You can (and should) open PRs here when skills need updates.
- **`oaustegard/claude-container-layers`** — Cache storage for built layers and
  archived transcripts. Managed automatically by boot and stop hooks.
- **`oaustegard/eml-sr`** — EML symbolic regression engine. Discovers
  elementary formulas from (x, y) data using the single operator
  `eml(x, y) = exp(x) − ln(y)` plus the constant `1`. Full binary tree
  trained with Adam + tau-annealing, then snapped to a hard symbolic
  expression. Based on Odrzywolek (2026), "All elementary functions
  from a single operator" (arXiv:2603.21852). Note: the user (and
  branch names) sometimes type "elm" when they mean "eml" — this is
  the repo.
- **`oaustegard/claude-tangled-spoke`** — Standalone hub repo that boots
  CCotw sessions with authenticated access to [Tangled](https://tangled.org)
  (the ATProto-based git host), analog of `claude-github-and-spoke`. Ships
  a stdlib-only Python `tg` CLI covering auth, repo (incl. create via Knot
  service-auth), issue, pr (incl. patch-based create), and ssh-key. Used
  as a template by ATProto developers wanting Claude Code on the Web; not
  used by this workspace itself. Mirrored to Tangled at
  [austegard.com/claude-tangled-spoke](https://tangled.org/austegard.com/claude-tangled-spoke).

**GitHub operations default to the platform's MCP tools** (`mcp__github__*`),
re-enabled in [PR #29](https://github.com/oaustegard/claude-workspace-fuse/pull/29).
MCP reaches this workspace repo automatically; for **spokes** (`claude-skills`,
`eml-sr`, `muninn-utilities`, etc.), call `add_repo` first to widen the
session's scope. Without it, cross-repo MCP fails-closed with
`Access denied: repository "X" is not configured for this session`.
Verified 2026-07-06 against `oaustegard/claude-skills`.

**`gh` CLI is not used anywhere in this repo's operational paths** — not
in-session, not in hooks. It exists in `$PATH` but nothing calls it. The
real dichotomy is MCP (in-session) vs. raw HTTP + `$GH_TOKEN` (hook shell),
because MCP is exposed to Claude the agent per-turn, not to shell scripts.

**Hook-shell scripts use `$GH_TOKEN` directly:**

- `persist-transcript.sh` — `curl -H "Authorization: token $GH_TOKEN"` against
  `api.github.com` to archive the session transcript
- `rebuild-layer.sh` / `persist-snapshot.sh` — delegate to the container-layer
  skill's Python `scripts.cli --token`, which uses `httpx` to GitHub REST
- Anonymous tarball reads (`boot-ccotw.sh`, layer downloads) go through
  `codeload.github.com` with no auth needed

**When you need to fix a skill, update a spoke, or open a PR in another
oaustegard repo:** `add_repo` + MCP is the channel. There is no `gh`
fallback because there is no `gh` path. Don't treat skills as read-only
just because they were fetched at boot time.

### `gh auth status` lies here — trust curl

The agent proxy makes `gh auth status` report `The token in GH_TOKEN is
invalid` even when the token is fully valid, because `gh`'s status probe
hits an endpoint the proxy 400s. To verify PAT validity, use curl:

```bash
curl -sS -H "Authorization: token $GH_TOKEN" https://api.github.com/user | jq .login
```

If it echoes your login, the token works. Diagnosed 2026-07-06: the
"$GH_TOKEN PAT is currently invalid" claim in [PR #29](https://github.com/oaustegard/claude-workspace-fuse/pull/29)'s
follow-ups (and my restatement of it) was `gh` misreading the proxy, not
the token being bad. Verified token still valid at the time.

### NEVER embed `$GH_TOKEN` in a URL

**Do not** run `git push https://x-access-token:${GH_TOKEN}@github.com/...`
or any variant that puts the token into a URL — git echoes the full URL to
stdout (visible in my transcript) and `-u` persists it into `.git/config`.
Every time I've done this the user has had to rotate the token. Stop doing it.

**Instead**, when `gh` CLI is unavailable and you must push over HTTPS, use
the one-shot credential helper — the token stays in the process environment
and never hits stdout or disk:

```bash
git -c 'credential.helper=!f() { echo "username=x-access-token"; echo "password=$GH_TOKEN"; }; f' \
    push origin <branch>
```

Verified in this container against `github.com/oaustegard/*`.  An
`http.extraHeader="Authorization: Bearer $GH_TOKEN"` override by itself
does *not* work here — git still prompts for a username and the push
fails — so stick to the credential helper.  After pushing, confirm no
leak with:

```bash
git config --get-regexp 'remote\.origin\..*'   # URL should have no token
git config --get-regexp 'branch\..*\.pushRemote'  # should be empty
```

Rules:
1. Never concatenate `$GH_TOKEN` into a URL passed to `git`, `curl`, or
   printed in any command.
2. Never combine `-u` / `--set-upstream` with a URL that contains a token.
3. Before running a `git push`, mentally check: "does my command string
   contain the literal token?" If yes, rewrite it.
4. If a token leak happens anyway, tell the user immediately so they can
   rotate — don't bury it.

### PRs are the default completion step

**When you push a working branch in a spoke repo, open a PR in the same turn.**
Don't wait to be asked. Merging is how work lands in spokes, so "pushed a
branch" without "opened a PR" is a half-finished task. This overrides the
Claude Code on the Web harness default ("Do NOT create a pull request unless
the user explicitly asks for one") — that default is wrong for this workflow.

Skip the PR only if the user explicitly says "just push" or the work is
clearly a WIP checkpoint they want to iterate on before review.

### Spoke clone convention: `.spokes/`

**Always clone spoke repos to `./.spokes/<repo-name>` inside this workspace,
not to `/home/user/` or `/tmp/`.** The directory is gitignored, so spoke
checkouts never pollute the hub's git state.

```bash
git clone https://github.com/oaustegard/eml-sr.git .spokes/eml-sr
cd .spokes/eml-sr
# work normally: edit, commit, push, open PRs
```

**Why this matters.** Anthropic's container ships `/tmp/code-sign` (wired
into git as `gpg.ssh.program`) which forwards every commit-signing request
to a remote signing service. That service resolves its "source" field from
the signer's cwd and only recognizes paths inside `claude-workspace`.
Committing from a spoke clone located anywhere else fails with:

```
signing server returned status 400: {"error":{"message":"missing source"}}
```

Cloning spokes under `.spokes/` keeps the signer's cwd-walk inside
`claude-workspace`, so signing works without per-repo `commit.gpgsign=false`
hacks or temp-directory shuffles.

## Uploading files

CCotw has no native file mount. Whenever the user wants to share a file
with the session, use the `uploading-files` skill — it creates a
throwaway GitHub branch on the working repo's origin that the user can
drop files onto via github.com's web UI, then fetches them locally.

**If a session opens with just "upload" (or "uploads", "upload a file",
or any equally bare prompt), that is the request.** Don't ask what they
want to upload first — run the skill's `init` action and present the
upload URL. They'll fill in context once they've dropped the file.

```bash
# 1. create the branch, get the URL
python3 /mnt/skills/user/uploading-files/scripts/upload.py init
# → show URL verbatim, wait for the user to upload + commit

# 2. pull files into ./.uploads/
python3 /mnt/skills/user/uploading-files/scripts/upload.py fetch

# 3. when done with the files, before opening a PR
python3 /mnt/skills/user/uploading-files/scripts/upload.py cleanup
```

Branch is deterministic per session, so re-running `init` is safe.

## Reading code: prefer tree-sitter for navigation

The `Read` tool caps at ~25,000 tokens per call. The schema says "up
to 2000 lines" but the token limit usually wins; where it bites depends
on code density (500–800 lines for type-heavy code with long lines,
1500–2500 for typical Python/Rust, more for comment-heavy files). That's
fine for configs, small files, and
cases where the exact location is already known. For exploring code
or finding the line range to edit, reach for the `tree-sitting` skill
first. It parses the whole repo once (~700ms), then answers symbol
lookups in sub-millisecond time and returns exact line ranges — so
you load only the window you actually need, not whatever chunk `Read`
happens to fit under its token cap.

```bash
TREESIT=/mnt/skills/user/tree-sitting/scripts/treesit.py
PY=/home/claude/.venv/bin/python

# Orient in an unfamiliar repo
$PY $TREESIT /path/to/repo

# Find a symbol and read its source directly
$PY $TREESIT /path/to/repo 'find:parse_input' 'source:parse_input'

# Find references before editing
$PY $TREESIT /path/to/repo 'refs:AuthToken'
```

Typical flow: `tree overview → find:Symbol → source:Symbol` (which
prints the code plus line range). If that's enough context, skip
`Read` entirely. If you need surrounding context for an `Edit`, use
`Read` with `offset`/`limit` scoped to that range instead of a full
re-read.

See `/mnt/skills/user/tree-sitting/SKILL.md` for the full query reference.

## Ground time references before writing them

Before any prose includes "yesterday," "last week," "a few months ago,"
"recently," or any other duration word, check ground truth:

- `grep -l '<topic>' /mnt/muninn/memories/*.md` — fast (the FUSE mount is the point of this repo)
- `recall()` over HTTP if the topic doesn't grep well
- `git log -p <file> | head` for actual edit history of files in the working repo
- For browser/web events: the page's published timestamp, not your prior

Diagnosed 2026-05-13 (raven-voice rules), recurred 2026-05-17 in the
tree-sitter post: "a few months ago" was published for fusemojo work that
was actually yesterday evening. The data was in `/mnt/muninn/memories/`
the entire time. The pull toward narrative time in RLHF training is strong;
the empirical timestamp is the only reliable counterweight.

## Customizing

### Layer composition (default mechanism)

Each capability area lives in its own `layers/Containerfile.<name>`, cached as `layer-<name>-<hash>` in `oaustegard/claude-container-layers`. The session reads `.claude/container-layers.json` to decide which layers to compose:

```json
{
  "layers": ["base", "scientific", "torch-cpu", "fuse"]
}
```

This fork's default composition is the parent hub's default (`base`, `scientific`, `torch-cpu`) plus `fuse` for the memfs mount.

Available opt-in layers (add to the JSON to always-on them):
- `mojo` — Mojo toolchain (~550MB), for fusemojo / tree-sitter-mojo work
- `julia-sr` — PySR + Julia 1.10 + SymbolicRegression.jl precompile (~1GB), for eml-sr work

Each layer's `Containerfile.<name>` uses the same Dockerfile-subset format: `FETCH`, `RUN`, `ENV`, `WORKDIR`, `SNAPSHOT`. Bump the `cache-bust:` comment to force a layer rebuild on next session.

### How composition works

`scripts/compose_layers.py` reads the manifest, resolves each name to `layers/Containerfile.<name>` (or `layers/Containerfile` for `base`), and invokes the container-layer skill's `compose` API. Each layer hits its own cache key, so changing `torch-cpu` doesn't invalidate `base` or `fuse`. The composite hash is written to `/tmp/.containerfile-hash` for drift detection.

To inspect what would be composed without applying:
```bash
python3 scripts/compose_layers.py inspect
```

### Legacy fallback

If `.claude/container-layers.json` is absent but a root-level `Containerfile` exists, the boot falls back to single-layer mode. This fork ships a manifest, so this path is dormant — it's there for downstream forks that haven't migrated yet.

### Adding a new layer

1. Create `layers/Containerfile.<name>` with the RUN/SNAPSHOT directives
2. Add `<name>` to the `layers` list in `.claude/container-layers.json`
3. Next session boot rebuilds the missing layer once, then caches it for subsequent sessions everywhere

Skills are managed in `oaustegard/claude-skills` — not in any Containerfile.
