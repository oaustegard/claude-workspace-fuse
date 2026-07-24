# Revoking muninn-verify-patch

This tool sends patches to the Anthropic API for structured review and persists
predictions/outcomes to a Turso database. Revocation has two surfaces:
credential rotation (stops future calls) and ledger erasure (removes already-
recorded predictions).

## Step 1 — Stop future verifications (credential rotation)

- `ANTHROPIC_API_KEY` — revoke at https://console.anthropic.com/settings/keys.
  Stops the model-invocation path. Without it, `verify_patch()` raises before
  any data is sent.
- `TURSO_TOKEN` — rotate via `turso db tokens revoke <name>` and reissue.
  Stops `stamp_verification` writes and `review_verifications` reads. The
  database itself remains intact unless explicitly destroyed.

The same `TURSO_TOKEN` is shared across all remembering-backed utilities
(memory-tfidf, remind, issue-close, perch-triage, zeitgeist-delta). Rotating
it disables ALL of them simultaneously.

## Step 2 — Remove already-recorded verifications

Verifications are stored as memory rows with type='verification' (or similar
tagging — check the latest schema). To purge:

- All verifications: a one-shot DELETE via the Turso CLI / SDK against the
  appropriate type filter.
- Single record: locate the tracking_id and delete that row.

The patch text and context ARE persisted in the memory record. If a verified
patch contains sensitive information (credentials, internal logic the user
later wants scrubbed), targeted deletion of that tracking_id is the remedy.

## Step 3 — Anthropic-side retention

Per Anthropic's commercial terms, request data is retained on their side per
the active retention policy (typically 30 days for non-ZDR accounts). The
verify-patch tool has no programmatic delete-on-vendor surface; the only
local control is rotating the API key so no further data is sent.
