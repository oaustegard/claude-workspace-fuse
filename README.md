# container-layer-test

**Test repo for [container-layer](https://github.com/oaustegard/claude-skills/tree/main/container-layer)** — custom, cached environment overlays for Claude's ephemeral containers.

## The Problem

Claude Code on the Web and Claude.ai both run in ephemeral containers that reset every session. Every time you start a conversation, your packages, skills, and configuration vanish. If your workflow depends on custom Python packages, fetched repos, or path configuration, you're re-installing everything from scratch — every single time.

## The Solution

A `Containerfile` (Dockerfile subset) that declares your environment, plus a caching layer that stores the built result as a GitHub Release asset. On subsequent sessions, a single tarball fetch replaces N individual installs.

## How It Works

```
Session starts
    → SessionStart hook fires boot-ccotw.sh
    → Script hashes the Containerfile (+ optional repo HEAD SHAs for invalidation)
    → Checks GitHub Releases for a cached tarball matching that hash
    → Cache hit?  → Single download + extract. Done in seconds.
    → Cache miss? → Execute each Containerfile instruction, snapshot the delta,
                    push tarball to GitHub Releases for next time.
```

## Repo Structure

```
.claude/settings.json   ← SessionStart hook triggers boot-ccotw.sh
boot-ccotw.sh           ← Bootstrap + restore/build entry point
Containerfile            ← Declarative environment spec (Dockerfile subset)
CLAUDE.md                ← Context for Claude about the environment
.gitignore               ← Excludes *.env credential files
```

## Containerfile Syntax

```dockerfile
FETCH github:user/repo /dest        # Fetch GitHub repo tarball
FETCH github:user/repo@ref /dest    # Specific branch/tag
RUN uv pip install --system pandas   # Shell commands (pip auto-detected for snapshot)
ENV KEY=value                        # Environment variables
WORKDIR /path                        # Set working directory
SNAPSHOT /path                       # Explicitly include path in cached layer

# Dockerfile instructions like FROM, EXPOSE, CMD are silently ignored.
```

## Setup for Your Own Repo

1. Copy `boot-ccotw.sh`, `Containerfile`, `.claude/settings.json`, and `CLAUDE.md` into your repo
2. Edit `Containerfile` to declare your environment
3. Optionally add a `.env` file with `GH_TOKEN=ghp_...` for caching
4. Open in Claude Code on the Web — the SessionStart hook does the rest

## Cache Storage

Cached layers are stored as release assets on a designated GitHub repo (default: `oaustegard/claude-container-layers`). The cache key is a SHA-256 of the Containerfile contents, optionally salted with dependency repo HEAD SHAs for automatic invalidation.

## Related

- **[container-layer skill](https://github.com/oaustegard/claude-skills/tree/main/container-layer)** — the underlying skill with parser, executor, and caching logic
- **[Blog post](https://austegard.com/blog/custom-container-layers-for-claudes-ephemeral-machines.html)** — the full story of why and how this was built
