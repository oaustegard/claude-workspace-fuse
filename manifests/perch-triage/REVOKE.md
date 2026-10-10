# Revoking muninn-perch-triage

This tool reads GitHub Flight Log discussions and (when auto_close=true)
closes the THUMBS_UP/LAUGH-reacted ones with a comment plus a memory write.
Revocation has surfaces for both — credential rotation stops everything,
but past auto-closes leave artifacts on GitHub and in Turso.

## Step 1 — Stop future triage runs (credential rotation)

- `GH_TOKEN` — revoke at https://github.com/settings/personal-access-tokens.
  Stops both reads and auto-close writes. **Primary kill.**
- `TURSO_TOKEN` — rotate at https://app.turso.tech/. Disables the auto-close
  path's memory write but the GitHub close still happens unless GH_TOKEN is
  also rotated. The recommendation-only path does not touch Turso.

The `GH_TOKEN` is shared across all the GitHub-writing utilities; rotate
carefully.

## Step 2 — Reverse already-auto-closed discussions

For each entry in past `auto_closed` results:

1. Reopen the GH discussion via the GitHub UI or GraphQL `unmarkDiscussionAsAnswered` /
   reopen mutation.
2. Edit or delete the closing comment (which references the memory id) via
   the GitHub UI.
3. Forget the corresponding memory in Turso via `forget(memory_id)` against
   the Muninn memory store.

The triage tool does not provide a bulk-undo; revocation is per-discussion.

## Step 3 — Uninstall the code

If installed via the manifest's `runtime.install`, delete the cloned tree.

## What this kill switch cannot do

- Cannot retract triage *recommendations* (those live in the caller's
  output, not on any persistent surface).
- Cannot edit reactions on discussions — the tool reads but does not modify
  reaction state.
