# Revoking muninn-task-policy

This tool is read-only: it loads policy from existing Turso rows (ops
entries, preference memories, perch-time run memories) and does not write
anything. Revocation is purely credential rotation — there is no data to
clean up that this tool produced.

## Step 1 — Stop future reads (credential rotation)

Rotate `TURSO_TOKEN` at https://app.turso.tech/. This immediately stops the
tool from reading policy. **Primary kill.**

`TURSO_TOKEN` is shared across all memory-touching utilities (`remembering`,
`remind`, `issue_close`, `memory_tfidf`, `news_watch`, `verify_patch`,
`zeitgeist_delta`, `perch_triage`'s auto-close path). Generate a new token
and update consumers before revoking the old.

## Step 2 — Uninstall the code

If installed via the manifest's `runtime.install` (in v0.4 the install is
`preinstalled`, so this means removing it from the muninn-utilities tarball
build), delete the module file `muninn_utils/task_policy.py` and the
manifests at `manifests/task-policy/`.

## What this kill switch cannot do

- Cannot retract policy decisions made by callers that consumed the loaded
  policy in past sessions — those live in the run memories / report outputs
  the caller wrote, which are separate concerns from this tool.
- Cannot revoke individual ops entries or preference memories; those are
  managed via `config_set('')` or the memory store's normal `forget`/
  `supersede` flows, not by this tool's kill switch.
