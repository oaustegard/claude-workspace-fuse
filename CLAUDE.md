# Claude Workspace

This repo configures Claude Code on the Web to boot as **Muninn**.

## What happens on session start

The `SessionStart` hook in `.claude/settings.json` runs `boot-ccotw.sh`, which:
1. Bootstraps the container-layer skill from `oaustegard/claude-skills`
2. Applies the `Containerfile` — fetching skills and installing packages
3. Caches the result as a tarball in GitHub Releases (if `GH_TOKEN` is set)
4. On subsequent sessions, restores from cache instead of rebuilding
5. Runs `post-boot.sh`, which calls the remembering skill's `boot()` to load the Muninn identity, profile, ops, and recent memories from Turso

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

## Customizing

Edit `Containerfile` to change what gets installed. The format is a
Dockerfile subset: `FETCH`, `RUN`, `ENV`, `WORKDIR`, `SNAPSHOT`.
