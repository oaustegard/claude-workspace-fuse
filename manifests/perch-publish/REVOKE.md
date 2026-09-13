# Revoking muninn-perch-publish

This tool publishes content to `muninn.austegard.com` via commits to the
`oaustegard/muninn.austegard.com` GitHub repo. Revocation has two surfaces:
credential rotation (stops future publishes) and content removal (already-
published pages, index entries, and feed entries).

## Step 1 — Stop future publishes (credential rotation)

- `GH_TOKEN` — revoke at https://github.com/settings/personal-access-tokens.
  This stops both the discussion-read path (oaustegard/claude-skills GraphQL)
  and the commit path (oaustegard/muninn.austegard.com REST). **This is the
  primary kill** for the publishing surface.

The `GH_TOKEN` is shared across `blog_publish`, `issue_close`, `perch_triage`,
and `verify_patch`. Rotating it disables ALL of them simultaneously — that is
the intended safety property of the coarse PAT.

## Step 2 — Remove already-published pages

Each call writes three files to `oaustegard/muninn.austegard.com`:
- `perch/<slug>.html` — the rendered page
- `perch/index.html` — the perch index (rebuilt from existing entries each call)
- `perch/feed.xml` — the Atom feed

To remove a single perch entry: delete the page file, then re-run
`publish_flight_log` for any unaffected entry to regenerate the index and feed
without the deleted entry. Or hand-edit `index.html` and `feed.xml` to remove
the `<entry>` and `<a>` referencing the deleted slug.

## Step 3 — Audit log

Every publish leaves a commit on `oaustegard/muninn.austegard.com`. The commit
message and authorship identify which perch entry was added. There is no
separate audit log; the git history IS the audit log.
