# Revoking muninn-zeitgeist-delta

This tool is read-only at the memory layer (no writes to Turso) and produces
no third-party persistence — it only sends embedding requests through
Cloudflare AI Gateway to Gemini and reads recent zeitgeist memories from
Turso. Revocation is purely about credential rotation.

## Step 1 — Stop future calls (credential rotation)

Three credential surfaces, any one of which kills the tool:

- `CF_API_TOKEN` — rotate at https://dash.cloudflare.com/profile/api-tokens.
  Stops the embedding-call path entirely. **Primary kill.**
- `TURSO_TOKEN` — rotate at https://app.turso.tech/. Stops the memory-read
  path; the tool can no longer fetch the prior zeitgeists to compare against.

Cloudflare AI Gateway logs (and possibly Gemini, depending on Cloudflare's
forwarding config) may retain the embedding-request payloads. Rotating the
CF token does not retract logged content — see Cloudflare's AI Gateway
retention docs.

## Step 2 — Uninstall the code

If installed via the manifest's `runtime.install`, delete the cloned tree.

## What this kill switch cannot do

- Cannot retract embedding requests already logged by Cloudflare or Gemini.
- Cannot affect any memory in Turso — this tool never writes there.
