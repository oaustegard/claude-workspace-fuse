# Revoking muninn-issue-close

This tool closes GitHub issues with a structured comment AND writes a
decision memory to the Muninn Turso DB. Revocation has two surfaces —
credential rotation (stops future closes + memory writes) and content
removal (handles already-posted comments and stored memories) — and v0.3
models them together as a single `kill_switch.manual`. This document
treats them as separate steps.

## Step 1 — Stop future closes (credential rotation)

Two credentials, both required. Rotate either to immediately stop new
closes:

- `GH_TOKEN` — revoke at https://github.com/settings/personal-access-tokens.
  Stops both the issue-close API call and the comment post.
- `TURSO_TOKEN` — rotate at https://app.turso.tech/. Stops the decision
  memory write but does NOT stop the GitHub close. If you rotate only this,
  future closes will still happen on GitHub but will record `detached_failures`
  for the memory write.

The `GH_TOKEN` is shared across `perch_publish`, `blog_publish`, `perch_triage`,
`verify_patch`, and this tool. Rotate carefully — generate a new token and
update the consumers before revoking the old.

## Step 2 — Remove already-closed-with-comment artifacts (irreversible at full-text)

- **GitHub comments:** edit or delete the closing comment via the GitHub UI
  or API. The issue can be reopened separately. Past closures are still in
  the issue's event log even after comment deletion.
- **Decision memories:** call `forget(memory_id)` or `supersede(...)` against
  the Turso store for each memory_id returned by past closes. The tool does
  not provide a bulk-undo; revocation is per-issue.

## Step 3 — Uninstall the code

If installed via the manifest's `runtime.install`, delete the cloned tree.

## Spec note

A v0.4 `kill_switch.steps: [...]` shape (each step its own kind) would let
this manifest declare "rotate GH_TOKEN AND TURSO_TOKEN, then optionally
delete past comments and memories" as a structured sequence rather than
prose. Filed in muninns-inbox discussion #1.
