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

**IMPORTANT: Always use `gh` CLI for GitHub operations — NEVER use MCP tools
(`mcp__github__*`).** The MCP GitHub server is hard-scoped to `claude-workspace`
only and WILL fail on every other repo. There is no way to change this — it's
a platform limitation. The `gh` CLI (authenticated via `$GH_TOKEN`) has no
such restriction and works across all oaustegard repos.

Use `gh` for ALL GitHub operations: releases, PRs, issues, file contents,
repo browsing, API calls — including for `claude-workspace` itself. Do not
reach for `mcp__github__*` tools even when they appear available. They exist
in the tool list but their repo scope cannot be expanded.

When you need to fix a skill, update a spoke, or open a PR in another repo —
do it directly via `gh`. Don't treat skills as read-only just because they
were fetched at boot time.

## Customizing

Edit `Containerfile` to change what system packages and Python deps get installed.
The format is a Dockerfile subset: `FETCH`, `RUN`, `ENV`, `WORKDIR`, `SNAPSHOT`.

Skills are managed in `oaustegard/claude-skills` — not in the Containerfile.
