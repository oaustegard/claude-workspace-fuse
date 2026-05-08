# Claude Workspace

This repo configures Claude Code on the Web to boot as **Muninn**.

## What happens on session start

The `SessionStart` hook in `.claude/settings.json` runs `boot-ccotw.sh`, which:
1. Bootstraps the container-layer skill from `oaustegard/claude-skills`
2. Applies the `Containerfile` — installing system packages and Python deps (cached as a tarball in GitHub Releases)
3. Fetches skills fresh from `oaustegard/claude-skills` via tarball (always current, never cached in the container layer)
4. Sets up Python paths for the remembering skill
5. Outputs `<available_skills>` XML frontmatter into the context window
6. Runs `post-boot.sh`, which calls the remembering skill's `boot()` to load the Muninn identity, profile, ops, and recent memories from Turso
7. Pulls `muninn_utils/*.py` from the mac repo (selectively, via GitHub Contents API) into `~/muninn_utils/`. Runs after `boot()` so canonical mac files override any Turso `utility-code` materialization for utilities already migrated. No-ops without `GH_TOKEN`.

Skills, the container layer, and muninn_utils are deliberately separated:
- **Container layer** (cached): slow-to-install system packages, CLI tools, Python libs
- **Skills** (fresh every session): fetched from `claude-skills`, never stale
- **muninn_utils** (fresh every session): fetched from `mac`, source-of-truth for Muninn-flavored code

## muninn_utils: mac is source-of-truth

Per memory `0d63ed4f`: muninn_utils used to live as `utility-code` memories
in Turso, materialized to `~/muninn_utils/` at boot via `install_utilities()`.
Source-of-truth has moved to files in `oaustegard/muninn.austegard.com`
(`muninn_utils/*.py`). Boot fetches them via the GH Contents API — only the
`.py` files at the directory root, not the 33MB full repo. Tests stay in mac
and run there.

Why not clone all of mac at boot? 99% of sessions don't need the blog HTML,
images, or perch outputs. Full clone would cost ~3-5s of boot time and ~33MB
of bandwidth for content only situationally useful. Sessions that genuinely
need full mac access (writing blogs, debugging perch) should lazy-clone to
`.spokes/mac` per the spoke convention below.

Turso `utility-code` memories remain as fallback for utilities not yet
migrated to mac — `install_utilities()` materializes them, then the mac
fetch overwrites the migrated ones with the canonical files. Migration in
progress: PR #124 on mac is the template (`blog_publish`, `bsky_card`,
`issue_close` migrated). Remaining: `bsky_limit`, `perch_publish`,
`verify_patch`, `remind`, `perch_triage`, `memory_tfidf`, `whtwnd`,
`function_name`.

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

**GitHub operations use `gh` CLI** (authenticated via `$GH_TOKEN`), which
works across all oaustegard repos — hub and spokes alike. The platform's
MCP GitHub server is denied in `.claude/settings.json` via
`deniedMcpServers` since it cannot reach spoke repos.

When you need to fix a skill, update a spoke, or open a PR in another repo —
do it directly via `gh`. Don't treat skills as read-only just because they
were fetched at boot time.

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

The `Read` tool caps at ~25,000 tokens per call (the schema says "up
to 2000 lines" but the token limit hits first on real code — usually
around 500–800 lines). That's fine for configs, small files, and
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

## Customizing

Edit `Containerfile` to change what system packages and Python deps get installed.
The format is a Dockerfile subset: `FETCH`, `RUN`, `ENV`, `WORKDIR`, `SNAPSHOT`.

Skills are managed in `oaustegard/claude-skills` — not in the Containerfile.
