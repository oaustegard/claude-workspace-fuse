# Revoking muninn-memory-tfidf

This tool reads from the Muninn memory store via Turso. It is read-only —
nothing is written to Turso, no third party is contacted, no state persists
in the tool's own storage between calls.

## Step 1 — Stop future reads (credential rotation)

Rotate `TURSO_TOKEN` at https://app.turso.tech/. This immediately stops the
tool from reading the memory database. **This is the primary kill.**

If `TURSO_TOKEN` is shared with other tools (the `remembering` skill itself,
`remind`, `verify_patch`, `zeitgeist_delta`), generate a new token first and
rotate the other tools' configurations before revoking the old one.

## Step 2 — Uninstall the code

If installed via the manifest's `runtime.install` (git clone of
`oaustegard/muninn-utilities` at the declared SHA, subpath `muninn_utils`),
delete the cloned tree.

## What this kill switch cannot do

- Cannot retract similarity scores or cluster assignments returned by past
  calls — those live in the caller's memory or output, not in the tool.
- Cannot affect the Turso DB contents; this tool never writes to it.
