#!/bin/bash
# UserPromptSubmit hook: recover a degraded boot by widening MCP repo scope.
#
# THE CHICKEN-AND-EGG
# -------------------
# boot-ccotw.sh (SessionStart) runs before any model turn, so it cannot call
# add_repo — the only in-session lever that adds a spoke repo to the CCotw
# proxy's GitHub scope. On a cold start the spokes (claude-skills,
# muninn-utilities, claude-container-layers) are out of scope; every codeload
# tarball 403s; boot dies without the container-layer skill, fresh skills,
# the remembering module, the memfs mount, or identity.
#
# A hook is a shell script and ALSO cannot call add_repo. But UserPromptSubmit
# hook stdout is concatenated into the prompt context uncapped — so this hook
# hands the model the exact recovery it must perform on its first turn. The
# model is the only surface that can call add_repo; this directive tells it to.
#
# Fires only when boot is actually degraded (memfs unmounted OR remembering
# absent). Silent on a healthy session. See CLAUDE.md "Boot recovery" and
# memories 74901b87 / 900d382b / 8d31c188.

set -e

# Healthy boot = memfs projecting memories AND the remembering skill present.
# If both hold, there is nothing to recover — stay silent.
if mountpoint -q /mnt/muninn 2>/dev/null && [ -d /mnt/skills/user/remembering ]; then
    exit 0
fi

cat <<'EOF'
<boot-recovery-directive priority="do-this-first">
Boot came up DEGRADED — the memfs mount and/or the remembering skill are
missing because the spoke repos were out of the session's GitHub scope at
SessionStart (a shell hook cannot call add_repo; you can). Before doing
anything else this turn, recover:

1. Call add_repo (mcp__Claude_Code_Remote__add_repo) for each of:
     - oaustegard/claude-skills
     - oaustegard/muninn-utilities
     - oaustegard/claude-container-layers
   add_repo alone opens the codeload/tarball channel, which is all boot needs.
   Do NOT `git clone` them and do NOT call register_repo_root — registering
   inlines each spoke's CLAUDE.md/skills into context and they cross-talk with
   this hub's instructions. Scope without inlining is the whole point.

2. Invoke the muninn-boot skill (Skill tool, name "muninn-boot"), or run it
   directly:  bash .claude/skills/muninn-boot/scripts/boot.sh
   It re-runs boot (now that scope is granted) and guarantees the memfs
   mount via a libfuse/fusepy fallback. (The skill wraps scripts/session-recover.sh.)

3. Confirm: `ls /mnt/muninn/memories | wc -l` should report ~2000+ memories,
   and the recovery output should show identity reloaded.

Do this silently and briefly — one line to the user that boot self-healed,
then proceed with their actual request. NOTE (docs-checked 2026-07-07): a CCotw
*environment* has no source-repo list — it carries only name/network/env-vars/
setup-script — so the spokes cannot be attached at the environment level. A
*session* CAN preselect multiple repos (claude.ai/code?repositories=<slugs>), a
candidate set-and-forget path, but whether that inlines each repo's CLAUDE.md is
untested; until it's verified this first-turn recovery IS the standing solution.
</boot-recovery-directive>
EOF
