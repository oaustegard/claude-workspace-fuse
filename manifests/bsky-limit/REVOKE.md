# Revoking muninn-bsky-limit

This tool is pure-compute (string truncation against a grapheme cap). It has
no credentials, no network access, no persistence. There is nothing to revoke
in the credential or content sense.

## Step 1 — Uninstall the code

If installed via the manifest's `runtime.install` (git clone of
`oaustegard/muninn-utilities` at the declared SHA, subpath `muninn_utils`),
delete the cloned tree.

## What this kill switch cannot do

There is nothing to undo. No state to clean up. No third party to notify.
Removing the module from the install host is the entire revocation surface.

## Spec note

install-manifest-spec v0.3 requires every tool to declare a `kill_switch`,
which is well-fitted for tools with credentials or persistent state but
overdoes it for pure-compute helpers. A v0.3.1 `kill_switch.kind: "stateless"`
shape would let this tool declare "nothing to revoke" honestly. Filed as a
finding in muninns-inbox discussion #1.
