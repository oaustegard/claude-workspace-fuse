# Turso 503 / DNS-cache diagnostic

## Why this exists

We're seeing intermittent **HTTP 503** responses from the Turso HTTP API
(`https://*.aws-us-east-1.turso.io/v2/pipeline`) when the `remembering`
skill makes requests from inside the Claude Code on the Web (CCotw)
container. The error bodies on those failures reference a **"dns cache"**
condition.

Turso support has confirmed that no part of their stack emits the phrase
"dns cache" in any error message. That points the finger at something
between the CCotw container and Turso — most likely the Anthropic-managed
forward proxy. Two environment variables in CCotw containers are
consistent with this hypothesis:

- `CLAUDE_CODE_PROXY_RESOLVES_HOSTS=true` — the proxy performs DNS
  resolution on the container's behalf.
- `CLAUDE_CODE_USE_CCR_V2=true` — the v2 "Claude Code Router" proxy is
  in the path.

`turso_probe.py` is the diagnostic that gathers evidence for a bug report
to Anthropic.

## What the probe does

Every `--interval` seconds (default 5s) the probe makes one fresh-socket
HTTPS request to each of:

| target | endpoint | role |
|---|---|---|
| `turso` | `POST {TURSO_URL}/v2/pipeline` with `SELECT 1` | the suspect |
| `control_cloudflare` | `GET https://1.1.1.1/cdn-cgi/trace` | Cloudflare anycast control |
| `control_github` | `GET https://api.github.com/zen` | non-Cloudflare control |
| `control_google` | `GET https://www.google.com/generate_204` | captive-portal control |

For every request it captures:

- `socket.getaddrinfo` time and the resolved IP set
- HTTPS request time, status code, **all** response headers, body preview
- For exceptions: type, message, and full traceback
- A regex scan (`/dns.*cache/i`) over the entire serialized record so the
  suspect phrase is impossible to miss whether it shows up in a header,
  body, or exception message

Connection pooling is disabled (`pool_connections=1, pool_maxsize=1`,
fresh `Session` per request) so every probe exercises the full
DNS-resolve → TCP-connect → TLS-handshake → HTTP-request path.

## Pacing rationale

Defaults are deliberately tame and well within the envelope of a normally
active Muninn session:

- 1 round / 5s = 4 requests / 5s = **0.8 req/s aggregate** across 4 hosts
- Per-host: **0.2 req/s** (one request every 5 seconds to any single host)
- 10-minute default run → ~120 requests per host

This is roughly 5× the request rate of a typical session that's actively
using `remember()` and `recall()` — fast enough to catch intermittent
failures within a reasonable window, gentle enough that no rate limiter
or operations dashboard should flag it.

## Running it

```bash
# Defaults: 10 minutes, 5s interval
python3 diagnostics/turso_probe.py

# Longer collection window
python3 diagnostics/turso_probe.py --duration 1800   # 30 min

# Gentler pacing
python3 diagnostics/turso_probe.py --interval 10
```

Requires `TURSO_URL` and `TURSO_TOKEN` to be set the same way the skill
reads them (env vars, `/mnt/project/turso.env`, `/mnt/project/muninn.env`,
or `~/.muninn/.env`).

## Output

Each run creates `diagnostics/runs/<UTC-timestamp>/` containing:

- `events.ndjson` — one JSON record per probe request, full capture
- `summary.md` — per-host outcome table, DNS-cache signature matches,
  worst non-OK samples, and a paste-ready bug-report copy block

The `runs/` directory is **not** gitignored — small evidence drops are
fine to commit. If you collect a very large run, attach the file to the
bug report instead of committing it.

## Filing the bug report

After a run that captures at least one failure (or one DNS-cache match):

1. Open the run's `summary.md` and copy the block under
   "Bug-report copy block".
2. File the report at <https://github.com/anthropics/claude-code/issues>
   (or via the user's normal Anthropic support channel for production
   container issues).
3. Attach the run's `events.ndjson` so Anthropic's network team can see
   the full per-request detail without having to reproduce.

The strongest single signals to highlight, in order:

1. **Quoted "dns cache" text** with `/etc/resolv.conf` showing only
   `8.8.8.8` — the container's resolver isn't the one emitting that
   message; the proxy is.
2. **Per-host failure-rate divergence**: if `turso` fails materially more
   often than the controls, the issue is target- or route-specific, not
   "general internet flakiness."
3. **Response-header stripping**: successful Turso responses come back
   with `server`, `via`, AWS-ALB, and Cloudflare headers all missing.
   That's a fingerprint of a transparent rewriting proxy in the path
   and contextualizes the 503s as proxy-generated, not origin-generated.
