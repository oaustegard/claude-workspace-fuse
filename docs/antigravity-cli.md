# Running the Antigravity CLI in the container

How to install, authenticate, and orchestrate Google's **Antigravity CLI**
(`agy`, v1.0.0, released at I/O 2026) inside this CCotw container.

## Verdict

`agy` **installs, authenticates, and runs non-interactively** here. It is a
single ~184 MB Go binary; `agy -p "<task>"` works as an orchestrated
sub-agent — verified end to end (it answered a coding prompt, reporting
itself as **Gemini 3.5 Flash**). Authentication is the work: there is no
API-key path, only Google OAuth, and the container lacks the D-Bus keyring
`agy` expects. Both are surmountable. Once a token file is in place every
`agy -p` call is silent.

## Install

```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
```

The installer is clean — queries a per-platform manifest JSON, downloads
the payload, **verifies a SHA-512 checksum**, then writes the binary to
`~/.local/bin/agy` (override with `--dir`) and appends a `PATH` export to
the shell rc files.

- Binary: `~/.local/bin/agy`, ~184 MB, ELF x86-64.
- Distribution: **not npm.** The `antigravity-cli` package on npm is a
  0.0.1 squatter — ignore it. Google ships only via `install.sh`.
- Self-updates in the background; re-running `install.sh` is a safe no-op.
- Repo `github.com/google-antigravity/antigravity-cli` is a feedback /
  changelog tracker only — no source.

> **Caveat — search-result injection.** A web search for install
> instructions returned a summary telling the reader to "download v1.23.2
> or lower, do not download a higher version." That is a malware-style
> version-pinning lure, not anything Google published. The real release is
> v1.0.0. Use the official `install.sh`.

## Command surface

`agy` with no arguments launches an interactive TUI. Orchestration-relevant
flags (`agy --help`):

| Flag | Purpose |
|---|---|
| `-p`, `--print`, `--prompt` | Run a single prompt non-interactively, print the response, exit |
| `--print-timeout` | Response-wait budget for print mode (default `5m`) |
| `--dangerously-skip-permissions` | Auto-approve every tool/permission request |
| `--add-dir` | Add a directory to the workspace (repeatable) |
| `-c`, `--continue` / `--conversation <id>` | Continue / resume a conversation |
| `-i`, `--prompt-interactive` | Seed an interactive TUI session with a first prompt |
| `--sandbox` | Run with terminal restrictions enabled |

Subcommands: `changelog`, `help`, `install`, `plugin`/`plugins`, `update`.
There is no `login`/`auth` subcommand — auth triggers lazily on the first
agent call.

**Flag ordering matters:** `-p`/`--print` consumes the next argument as the
prompt. Put other flags *before* `-p`, or make `-p "..."` last. Otherwise
`agy -p "task" --dangerously-skip-permissions` folds the flag silently into
the prompt text.

## Authentication

`agy` authenticates only via Google OAuth — there is **no API-key
environment variable**. Two independent problems must be solved to run it
headless.

### Problem 1 — the auth prompt blocks

On the first agent call with no stored token, `agy` runs an OAuth flow:

- **Print mode (`agy -p`)** prints the `accounts.google.com` URL and waits
  **30 seconds** for a pasted authorization code, then aborts. The 30 s is
  hardcoded (`printmode.waitForAuth`); `--print-timeout` does *not* extend
  it. Too short for any human-in-the-loop round trip through chat.
- **Interactive mode (`agy -i`, the TUI)** has **no auth timeout** — it
  waits indefinitely. This is the usable path, but it is a full-screen TUI
  that must be driven through a pseudo-terminal.

`scripts/agy_auth_broker.py` drives it: spawns `agy -i` under a pty,
answers the terminal capability queries so the TUI renders, auto-selects
"Google OAuth" from the login menu, scrapes the OAuth URL to a file, and
types back an authorization code dropped into a file. A human opens the
URL, consents, and the broker feeds the code.

### Problem 2 — token storage needs a keyring

By default `agy` saves the token to the OS keyring, which needs D-Bus. The
container has no D-Bus, so the keyring write fails silently
(`keyringAuth: ... "dbus-launch": executable file not found`) and the token
dies with the process. The fix: `agy` switches to **file-based token
storage when it detects an SSH session**. Set fake SSH env vars before
launching it:

```bash
export SSH_CONNECTION="203.0.113.1 50000 203.0.113.2 22"
export SSH_TTY="/dev/pts/0"
export SSH_CLIENT="203.0.113.1 50000 22"
```

`agy` then logs `Using file-based token storage because SSH session
detected` and writes a file instead.

### The token file

`agy` reads/writes its credential at
`~/.gemini/antigravity-cli/antigravity-oauth-token`, as JSON:

```json
{
  "token": {
    "access_token": "ya29....",
    "token_type": "Bearer",
    "refresh_token": "1//04....",
    "expiry": "2026-05-20T17:19:27.000000000Z"
  },
  "auth_method": "consumer"
}
```

Once this file exists (with SSH env set so `agy` consults a file, not the
keyring), every `agy -p` call is silent — `agy` refreshes the access token
from `refresh_token` on its own.

### The catch — ephemeral containers

CCotw containers pause on session inactivity, which kills any live `agy`
process mid-auth. The interactive broker only works if the human completes
the OAuth dance promptly (under ~3-4 min) — a slow dance loses the process.
The durable answer: do the dance once, **save the resulting
`antigravity-oauth-token` file**, and re-write it into
`~/.gemini/antigravity-cli/` on each fresh container. The `refresh_token`
is the durable part; a stale access token is fine, `agy` refreshes it.

## State & the Gemini lineage

`agy` reuses the **Gemini CLI config tree** — concrete proof of the shared
harness. Everything lands under `$HOME`, nothing in git:

```
~/.gemini/config/mcp_config.json          # shared MCP server config
~/.gemini/config/projects/<uuid>.json     # per-project (folder URI, allowWrite)
~/.gemini/config/.migrated                # Gemini-CLI → Antigravity migration flag
~/.gemini/antigravity-cli/antigravity-oauth-token  # the credential (see above)
~/.gemini/antigravity-cli/conversations/  # conversation history (for --conversation)
~/.gemini/antigravity-cli/{brain,knowledge}/
```

`agy` also drops a `.antigravitycli/` directory **in the working repo** — a
symlink to the global project JSON. It is gitignored here; downstream forks
should do the same.

## Orchestration

With the token file in place, `agy -p` is a non-interactive sub-agent — the
same sub-process shape this workspace uses for Gemini via `invoke-gemini`.
Verified working:

```bash
export SSH_CONNECTION="203.0.113.1 50000 203.0.113.2 22"   # → file token storage
agy --dangerously-skip-permissions -p "<task>"
```

An orchestrator (Claude Code, a `flowing` DAG) shells out, captures stdout,
and folds the result back — a second-opinion agent on Google's harness
(Gemini 3.5 Flash) alongside Claude's. `agy` reads
`~/.gemini/config/mcp_config.json`, so it can be handed the same MCP
servers as the rest of the fleet. Network: runtime calls go to
`cloudcode-pa.googleapis.com` (confirmed reachable once authenticated).

### Three ways to provision auth, worst to best

1. **Interactive broker per container** — `scripts/agy_auth_broker.py` plus
   one human OAuth dance. Works, but the dance must be prompt and repeats on
   every fresh container.
2. **Persist the token file** — do the dance once, save
   `antigravity-oauth-token`, re-write it on each container boot. No further
   dances. Caveat: it ships a personal Google credential into ephemeral
   containers — keep it out of git and out of logs.
3. **GCP service account (ADC)** — the binary references
   `GOOGLE_APPLICATION_CREDENTIALS` / `GOOGLE_CLOUD_PROJECT`; the
   `cloud-platform` scope and the "connect your GCP project" enterprise path
   imply a fully non-interactive service-account option. Unverified here (no
   GCP project to test) but it is the *correct* answer for unattended
   orchestration — no keyring, no personal token, no dance.

### Recommendation

`agy` is a working headless peer agent in this container today via options
1–2. For durable, unattended CCotw orchestration, option 3 (service
account) is worth verifying — it sidesteps both the keyring problem and the
personal-credential hygiene issue. Until then, option 2 (a persisted token
file) is the practical path.
