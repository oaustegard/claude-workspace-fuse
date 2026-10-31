# Revoking muninn-inbox-heartbeat

This tool is pure compute: it validates and mutates an in-memory state dict
that the caller passes in. It holds no credentials, makes no network calls and
persists nothing.

## Step 1: Uninstall the code

Delete the `muninn_utils/inbox_heartbeat.py` module from the install host
(the clone of `oaustegard/muninn-utilities` at the declared SHA).

## What this kill switch cannot do

Nothing to undo. Any `last_checked` values already written by callers are
ordinary state; removing the module does not change them.
