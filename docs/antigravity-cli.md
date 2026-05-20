# Running the Antigravity CLI in the container

Findings from installing and probing Google's **Antigravity CLI** (`agy`,
v1.0.0, released at I/O 2026) inside this CCotw container, and an honest
assessment of whether it can be wielded as part of agent orchestrations.

## Verdict

`agy` **installs and runs** in the container with no fuss — it is a single
static-ish Go binary, the install endpoints are reachable, and it has a
real non-interactive `--print` mode shaped exactly like `claude -p` /
`gemini -p`. **The blocker is authentication.** Every agent call requires a
Google OAuth login; there is no API-key environment variable. So `agy` is
*installable* headless but not *usable* headless without first solving the
credential problem (see [Orchestration](#orchestration)).

## Install (verified)

```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
```

The installer is worth reading before piping to a shell — it is clean:
queries a per-platform manifest JSON, downloads the payload, **verifies a
SHA-512 checksum against the manifest**, and only then writes the binary.
It drops `agy` into `~/.local/bin/` (override with `--dir`) and appends a
`PATH` export to `.bashrc`/`.zshrc`/`.profile`.

- Binary: `~/.local/bin/agy`, ~184 MB, ELF x86-64, dynamically linked.
- Distribution: **not npm.** The `antigravity-cli` package on npm is a
  0.0.1 squatter — ignore it. Google ships only via `install.sh` (and the
  Windows `.ps1` / `.cmd` variants).
- The binary self-updates in the background; re-running `install.sh` when
  `agy` already exists is a safe no-op.
- Repo `github.com/google-antigravity/antigravity-cli` is a feedback /
  changelog tracker only — README, CHANGELOG, demo gif. No source.

> **Caveat — search-result injection.** A web search for install
> instructions returned a summary telling the reader to "download v1.23.2
> or lower, do not download a higher version." That is a malware-style
> version-pinning lure, not anything Google published. The real current
> release is v1.0.0. Disregard any such advice; use the official
> `install.sh`.

## Command surface

`agy` with no arguments launches an interactive TUI. The orchestration-
relevant flags (`agy --help`):

| Flag | Purpose |
|---|---|
| `-p`, `--print`, `--prompt` | Run a single prompt non-interactively, print the response, exit |
| `--print-timeout` | Wait budget for print mode (default `5m`) |
| `--dangerously-skip-permissions` | Auto-approve every tool/permission request |
| `--add-dir` | Add a directory to the workspace (repeatable) |
| `-c`, `--continue` | Continue the most recent conversation |
| `--conversation <id>` | Resume a conversation by ID |
| `-i`, `--prompt-interactive` | Seed an interactive session with a first prompt |
| `--sandbox` | Run with terminal restrictions enabled |

Subcommands: `changelog`, `help`, `install`, `plugin`/`plugins`, `update`.
There is **no `login`/`auth` subcommand** — auth is triggered lazily on the
first agent call. `/logout` is a slash command inside the TUI.

## The authentication gate

This is the crux. `agy -p "..."` with no stored credentials prints:

```
Authentication required. Please visit the URL to log in:
  https://accounts.google.com/o/oauth2/auth?...&scope=cloud-platform+userinfo.email+...
Waiting for authentication (timeout 30s)...
Or, paste the authorization code here and press Enter:
```

- It waits 30 s for either a localhost OAuth callback **or** a manually
  pasted authorization code, then aborts.
- The remote/SSH paste-the-code path **does** work for a human-in-the-loop:
  open the URL in a browser, consent, paste the code back. The OAuth
  request uses `access_type=offline`, so a refresh token is issued.
- Requested scopes: `cloud-platform`, `userinfo.email`, `userinfo.profile`,
  `cclog`, `experimentsandconfigs`, `openid`.
- **No API-key path.** There is no `GEMINI_API_KEY` / `ANTIGRAVITY_API_KEY`
  equivalent. The binary *does* reference `GOOGLE_APPLICATION_CREDENTIALS`
  and `GOOGLE_CLOUD_PROJECT`, and the `cloud-platform` scope plus the
  "connect your GCP project" enterprise onboarding strongly suggest an
  Application-Default-Credentials path exists — but that is **unverified**
  (auth blocks before any agent call can confirm it).

## State, config, and the Gemini lineage

`agy` reuses the **Gemini CLI config tree** — concrete proof of the shared
harness the blog post describes. Nothing lands in git; it all goes to
`$HOME`:

```
~/.gemini/config/mcp_config.json        # shared MCP server config
~/.gemini/config/projects/<uuid>.json   # per-project (folder URI, allowWrite)
~/.gemini/config/.migrated              # Gemini-CLI → Antigravity migration flag
~/.gemini/antigravity-cli/conversations/  # conversation history (for --conversation)
~/.gemini/antigravity-cli/{brain,knowledge}/
~/.gemini/antigravity-cli/{keybindings.json,installation_id,cli.log}
```

It also drops a `.antigravitycli/` directory **in the working repo** —
just a symlink to the global project JSON. It is gitignored in this repo;
any downstream fork should do the same.

Credentials were not written (auth never completed). The README says the
CLI uses the "system keyring"; this container has no Secret Service
daemon, so it would fall back to a file under `~/.gemini/` — location
unconfirmed.

## Network allowlist requirements

The container's network policy must permit:

| Host | Phase |
|---|---|
| `antigravity.google` | install script, OAuth callback |
| `antigravity-cli-auto-updater-*.run.app` | install payload, self-update |
| `accounts.google.com`, `oauth2.googleapis.com` | OAuth |
| `www.googleapis.com` | userinfo |
| `cloudcode-pa.googleapis.com` | **runtime agent calls** |

Install-phase hosts are reachable from this environment today. The runtime
host `cloudcode-pa.googleapis.com` (the same Cloud Code backend Gemini CLI
uses) is unverified — auth blocked before a call could be made.

## Orchestration

`agy -p` is the same sub-process shape this workspace already uses for
Gemini via the `invoke-gemini` skill. The mechanical pattern:

```bash
agy -p "<task>" \
    --add-dir /home/user/claude-workspace-fuse \
    --dangerously-skip-permissions \
    --print-timeout 10m
```

An orchestrator (Claude Code, or a `flowing` DAG) shells out, captures
stdout, and folds the result back in — a second-opinion agent running
Google's harness alongside Claude's. `agy` also reads
`~/.gemini/config/mcp_config.json`, so it can be handed the same MCP tool
servers as the rest of the fleet.

**But the auth gate decides whether this is real.** Three options, worst
to best for unattended use:

1. **Persist a personal OAuth token.** Complete the paste-code flow once,
   then capture the refresh-token blob `agy` caches under `~/.gemini/` and
   re-inject it into each ephemeral container. Feasible (offline access is
   granted) but fragile, and it means shipping Oskar's personal Google
   credential into throwaway containers — a credential-hygiene cost.
2. **GCP service account (ADC).** If `agy` honours
   `GOOGLE_APPLICATION_CREDENTIALS` for the `cloud-platform` scope — likely
   but unverified — drop a service-account key, set
   `GOOGLE_CLOUD_PROJECT`, and it is fully non-interactive. This is the
   *correct* orchestration path. It needs a GCP project with the
   Antigravity/Gemini backend enabled and billing attached.
3. **Don't orchestrate it headless.** Use `agy` interactively in a local
   terminal and rely on Antigravity 2.0's conversation-import to move work
   between surfaces. The CLI's stated niche is keyboard-driven local and
   SSH use, not unattended CI.

### Recommendation

Until the ADC path is confirmed, `agy` is **not** a clean drop-in for
unattended CCotw orchestration the way `invoke-gemini` (plain API key) is.
It is a good fit for *attended* sessions and for a properly GCP-provisioned
environment. The next concrete step to make it orchestration-grade is to
verify option 2: provision a service-account key and test whether
`agy -p` runs non-interactively with `GOOGLE_APPLICATION_CREDENTIALS` set.
If that works, `agy` becomes a first-class peer agent; if it doesn't,
treat it as an interactive-only tool.
