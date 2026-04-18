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

Skills and the container layer are deliberately separated:
- **Container layer** (cached): slow-to-install system packages, CLI tools, Python libs
- **Skills** (fresh every session): fetched from GitHub, never stale

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
one of these two patterns — the token stays in the process environment and
never hits stdout or disk:

```bash
# preferred: extraHeader, single command
git -c http.extraHeader="Authorization: Bearer $GH_TOKEN" \
    push origin <branch>

# alternative: one-shot credential helper (useful if extraHeader gets stripped)
git -c credential.helper='!f() { echo "username=x-access-token"; echo "password=$GH_TOKEN"; }; f' \
    push origin <branch>
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

## Customizing

Edit `Containerfile` to change what system packages and Python deps get installed.
The format is a Dockerfile subset: `FETCH`, `RUN`, `ENV`, `WORKDIR`, `SNAPSHOT`.

Skills are managed in `oaustegard/claude-skills` — not in the Containerfile.
