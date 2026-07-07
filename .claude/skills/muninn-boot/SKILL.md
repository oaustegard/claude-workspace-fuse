---
name: muninn-boot
description: Boot (or recover a degraded boot of) the Muninn FUSE workspace — fetch skills + muninn-utilities, mount the /mnt/muninn memory corpus, and load Muninn identity. Invoke on the first message of a fresh session when boot came up degraded, or any time /mnt/muninn is missing or identity is absent. On a cold start the model MUST call add_repo for the three spokes first (see below); this is the one step a SessionStart hook cannot do. Skip only if the message says "skip boot".
---

# Muninn Boot (FUSE variant)

Boots **this** workspace — the FUSE fork. Distinct from the parent project's
`muninn-boot` in `muninn-utilities`, which does none of the fuse-specific work
(no `/mnt/muninn` mount, no container-layer compose, no fuse deps) and reads
`/mnt/project/*.env` files that don't exist in this CCotw environment.

## When boot already succeeded (warm resume)

If `/mnt/muninn` is mounted **and** `/mnt/skills/user/remembering` exists, the
`SessionStart` hook already booted this session — there is nothing to do.
Running `scripts/boot.sh` in that state is a cheap no-op that reports healthy.
This is the common case on container resumes, where `add_repo` scope from an
earlier turn persists.

## When boot came up degraded (cold start)

On a **cold** start the spoke repos are outside this session's GitHub scope, so
every `codeload` fetch 403s and the `SessionStart` hook boots degraded: no
skills, no `remembering`, no `/mnt/muninn`, no identity. The fix has one
model-only step the shell cannot perform, then a script:

1. **Call `add_repo`** (`mcp__Claude_Code_Remote__add_repo`) for each of:
   - `oaustegard/claude-skills`
   - `oaustegard/muninn-utilities`
   - `oaustegard/claude-container-layers`

   `add_repo` alone opens the codeload channel — all boot needs. Do **not**
   `git clone` them and do **not** call `register_repo_root`: registering
   inlines each spoke's `CLAUDE.md`/skills into context, where they cross-talk
   with this hub's instructions. Scope without inlining is the point.

2. **Run the boot:**

   ```bash
   bash "$CLAUDE_PROJECT_DIR/.claude/skills/muninn-boot/scripts/boot.sh"
   ```

   It confirms scope landed, re-runs the full fuse boot idempotently
   (`boot-ccotw.sh`), and guarantees the `/mnt/muninn` mount via a
   `libfuse2`/`fuse`/`fusepy` apt+pip fallback for a cold fuse-layer cache.

3. **Confirm:** `ls /mnt/muninn/memories | wc -l` should report ~2000+ memories
   and the output should show identity reloaded. Then one line to Oskar that
   boot self-healed, and proceed with his request.

## Why a skill and not only a hook

The `SessionStart` hook is a shell script that runs before any model turn, so
it cannot call `add_repo`. This skill is the model-invocable entrypoint that
can — packaging the "widen scope, then boot" sequence the hook can't express.
The hook is kept (hybrid) so warm resumes still auto-boot with zero effort; the
skill carries cold starts. There is no persistent "environment sources" lever
in this CCotw setup — this first-turn path is the standing solution.
