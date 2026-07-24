---
name: muninn-boot
description: Boots Muninn — runs scripts/boot.sh, which fetches oaustegard/claude-skills and oaustegard/muninn-utilities from their main branches (dynamic sideload), loads the Turso and GitHub tokens, and runs the memory-system boot sequence. Trigger on the first message of any new conversation in the Muninn project, or when the user says "boot up" / "boot" — unless the message contains "skip boot". If the message contains "skinny boot", run with BOOT_MODE=perch. Safe to run on every message: a warm container fast-exits in ~0s via a sentinel, so re-running is cheap and idempotent.
---

# Muninn Boot

Oskar's own repos and credentials (oaustegard/*, /mnt/project/*.env). Standing
procedure — runs every session.

```bash
bash /mnt/skills/user/muninn-boot/scripts/boot.sh
```

Skinny boot ("skinny boot" in the message):

```bash
BOOT_MODE=perch bash /mnt/skills/user/muninn-boot/scripts/boot.sh
```

`scripts/boot.sh` (~35 lines, sibling of this file — readable before running)
does, in order:

1. Fetches oaustegard/claude-skills → /mnt/skills/user and
   oaustegard/muninn-utilities → /home/claude/muninn-utilities, each at
   current main HEAD (dynamic — no pinned SHA).
2. Sources the two env files `boot()` reads: `Turso.env` (memory, config,
   reminders) and `GitHub.env` (GH_TOKEN for the RECENT FLIGHTS block, which
   degrades to empty without it).
3. Writes the `.pth` so `from scripts import boot` resolves, runs `boot()`,
   prints its output, and writes the sentinel (last, only on success).

## Credential scope

The remaining project `.env` files (`bsky.env`, `muninn-bsky.env`,
`strava.env`, `proxy.env`, `claude.env`) are used by later task-specific
steps, which source them inline immediately before the command that needs
them:

```bash
set -a; . /mnt/project/strava.env 2>/dev/null; set +a
```

(Env vars do not persist across separate `bash_tool` calls, so per-call
sourcing is how every consumer works regardless of what boot loads.)

## Dynamic sideload (no pins)

`CLAUDE_SKILLS_REF` / `MUNINN_UTILS_REF` at the top of `scripts/boot.sh` are
`main`, not pinned SHAs — the point of sideloading is that skill/utility
updates land on the next cold boot with no version bump and no re-upload of
this skill. The cost is that `main` runs as-is, unreviewed, so keep both repos
deployable on `main`.

A warm container will not re-pull mid-session (the sentinel short-circuits it);
`rm /home/claude/.muninn-booted` forces a fresh pull of `main`. This skill file
itself is still the one exception that must be re-uploaded to the project when
*it* changes, since the running copy is the project upload, not the fetched one.
