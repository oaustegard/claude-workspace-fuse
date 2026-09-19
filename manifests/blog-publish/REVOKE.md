# Revoking muninn-blog-publish

This tool publishes content to `austegard.com` via commits to a GitHub repo
AND optionally posts an announcement to Bluesky AND optionally appends an
engagement-link commit referencing the bsky post. Revocation has three
surfaces — credential rotation (stops future publishes/announces), content
removal (already-published pages and feed entries), and bsky-post deletion
(already-announced posts). v0.3 models them as a single `kill_switch.manual`;
this document treats them as separate steps.

## Step 1 — Stop future publishes (credential rotation)

- `GH_TOKEN` — revoke at https://github.com/settings/personal-access-tokens.
  This stops both the page-commit path and the feed-update path. **This is
  the primary kill** for the publishing surface.
- `MUNINN_BSKY_APP_PASSWORD` — delete at https://bsky.app/settings/app-passwords.
  Stops only the bsky-announce chain. The page still publishes if GH_TOKEN
  is valid.

The `GH_TOKEN` is shared across `perch_publish`, `issue_close`, `perch_triage`,
`verify_patch`, and this tool. Rotate carefully — generate a new token and
update the consumers before revoking the old.

## Step 2 — Remove already-published content (irreversible action)

- **Public web:** the rendered page at `https://austegard.com/<path>` and
  any feed entry pointing at it. Remove by committing a deletion of the file
  (and a feed rebuild that no longer references it). The tool has no
  `unpublish` action; this is a manual git operation.
- **Git history:** the publish commits stay in the repo's history forever
  unless you force-push a rewritten history (almost never worth it).
- **Crawlers / archives:** `austegard.com` is publicly readable; treat any
  publish as permanently public.

## Step 3 — Delete already-announced bsky posts

If the bsky chain ran, the announce post lives at the AT-URI returned in
`bsky_post.uri`. Use `bsky_card`'s `delete_post` action against that URI to
retract. The follow-up engagement-link commit on the GitHub repo remains
unless separately reverted; the dangling reference is harmless but stale.

## Step 4 — Uninstall the code

If installed via the manifest's `runtime.install`, delete the cloned tree.

## Spec note

A v0.4 `kill_switch.steps: [...]` shape (each step its own kind), plus a
`writes[]` shape that distinguishes user-service-public-readable persists
from third-party transmits, would let this manifest declare the three
revocation surfaces structurally rather than in prose. Filed in
muninns-inbox discussion #1.
