# Revoking muninn-whtwnd

This tool publishes blog entries to the user's PDS as `com.whtwnd.blog.entry`
records that federate to the WhiteWind AppView. Revocation has two surfaces
— credential rotation (stops future entries) and content removal (already-
published entries are public).

## Step 1 — Stop future publishes (credential rotation)

Delete `BSKY_APP_PASSWORD` at https://bsky.app/settings/app-passwords. This
immediately stops the tool from authenticating to the PDS — no new entries,
no edits, no deletes, no blob uploads. **This is the primary kill.**

`BSKY_HANDLE` is not a secret and does not need rotation; it just identifies
the account. The same handle+password is used by `bsky_card`, the
`blog_publish` bsky-announce chain, and any other atproto-credential tool —
deleting the password rotates them all.

## Step 2 — Remove already-published entries

Past entries live as records on the user's PDS. Remove via the `delete`
action against the rkey (or via any other ATProto client). Federated copies
on whtwnd.com and any third-party AppView mirror will eventually drop the
record but propagation is not instantaneous.

Image blobs uploaded via `upload_image` and embedded in entries are removed
when the embedding entry is deleted, but only after the PDS's garbage
collection cycle. Orphan blobs (uploaded but never embedded) are GC'd
automatically.

## Step 3 — Uninstall the code

If installed via the manifest's `runtime.install`, delete the cloned tree.

## What this kill switch cannot do

- Cannot retract entries already cached by external AppViews, archives, or
  search indexers.
- Cannot edit federated copies that have been replicated by self-hosted
  WhiteWind instances.
- The `kill_switch.kind: url` declaration covers the credential surface
  only; content removal is a separate manual step not modeled in v0.3.
