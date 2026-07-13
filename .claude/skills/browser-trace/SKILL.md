---
name: browser-trace
description: Capture a real browser network trace inside Claude Code on the Web (CCotw) — every host/request/body a page makes — when Playwright's Chromium can't reach anything through the agent proxy (net::ERR_CONNECTION_RESET). Use when you need to see what a page actually loads at runtime (analytics/trackers, third-party calls, upload endpoints), audit a site's privacy/security behavior, or drive a form and observe its traffic. Also the fix for "Chromium works nowhere in CCotw but curl works fine."
---

# browser-trace

Runtime network tracing for a real browser in CCotw, plus the fix for the
Chromium-can't-reach-anything problem that blocks it.

## The problem it solves

In CCotw, outbound HTTPS goes through a policy egress proxy (`$HTTPS_PROXY`)
that **re-terminates TLS**. Recent Chromium (≥131, including Playwright's
bundled build — confirmed on **Chromium 141**) sends a **post-quantum key
share (X25519MLKEM768)** in its TLS ClientHello. The egress terminator resets
that handshake, so *every* navigation fails with:

```
net::ERR_CONNECTION_RESET
```

The netlog tells the real story — the CONNECT tunnel opens (`HTTP/1.1 200
Connection Established`) and then the TLS handshake to the origin is reset:

```
{"net_error": -101, "os_error": 104}                       # ECONNRESET
{"error_lib": 35, "error_reason": 101, "ssl_error": 1,      # at the TLS layer
 "file": "net/socket/socket_bio_adapter.cc"}
```

`curl -x $HTTPS_PROXY` and Node's `https` tunnel through the same proxy **fine**,
because their ClientHello is smaller and carries no PQ share. Chromium flags
that supposedly disable PQ (`--disable-features=PostQuantumKyber`,
`EncryptedClientHello`, `--disable-quic`, forcing TLS 1.2) did **not** fix it in
testing.

## The fix (which is also the trace)

Interpose a tiny local MITM proxy. Chromium does TLS to **us** (localhost — we
accept its PQ hello happily), and **we** re-originate each request outward
through the agent proxy the way curl/Node do:

```
Chromium --TLS (self-signed cert, --ignore-certificate-errors)--> trace-proxy
         --plaintext, we log it--> Node CONNECT tunnel via $HTTPS_PROXY --> origin
```

Because the proxy terminates TLS, it sees every request in plaintext: host,
method, path, and optionally bodies. That *is* the network trace.

## Quick start

```bash
SK=/mnt/skills/user/browser-trace/scripts          # or .claude/skills/... in the hub
D=$(mktemp -d)

# 1. one-time self-signed cert for the proxy (SAN irrelevant; certs are ignored)
openssl req -x509 -newkey rsa:2048 -keyout "$D/mitm.key" -out "$D/mitm.crt" \
  -days 2 -nodes -subj "/CN=trace-proxy" \
  -addext "subjectAltName=DNS:localhost,DNS:*.com,DNS:*.net,DNS:*.io" 2>/dev/null

# 2. start the proxy (prints MITM_PORT=<n>, writes $D/trace.json every 0.5s)
TRACE_DIR="$D" node "$SK/trace-proxy.js" > "$D/proxy.out" 2>&1 &
sleep 2; cat "$D/proxy.out"

# 3. drive Chromium through it
node "$SK/run-trace.js" "https://example.com/" "$(cat "$D/mitm.port")"

# 4. ground-truth trace (server-side, every request the proxy relayed)
python3 -c "import json,collections; \
  c=collections.Counter(e['host'] for e in json.load(open('$D/trace.json'))); \
  [print(n,h) for h,n in c.most_common()]"

# 5. stop
pkill -f trace-proxy.js
```

## Environment knobs (trace-proxy.js)

| Var | Default | Purpose |
|---|---|---|
| `TRACE_DIR` | cwd | where `mitm.port`, `trace.json`, `bodies/` go |
| `MITM_KEY` / `MITM_CRT` | `$TRACE_DIR/mitm.{key,crt}` | the self-signed pair |
| `CCR_CA` | `/root/.ccr/ca-bundle.crt` | CA to verify real origins |
| `CAPTURE_BODIES` | off | save non-GET request bodies to `bodies/` |
| `BODY_HOSTS` | `filestack\|amazonaws\|\.s3\|upload\|spreedly` | which hosts' bodies to save |

## Chromium launch flags that matter (run-trace.js)

- `proxy.server: 'http://127.0.0.1:<MITM_PORT>'` — point at the trace-proxy, **not** `$HTTPS_PROXY`.
- `--ignore-certificate-errors` + context `ignoreHTTPSErrors: true` — trust the proxy's self-signed cert.
- `--disable-quic` — force TCP so nothing escapes via UDP/HTTP-3.
- `--no-sandbox`, `--disable-background-networking`, `--disable-component-update` — quiet the noise.
- `executablePath: '/opt/pw-browsers/chromium'` — CCotw's pre-installed Chromium (never `playwright install`).

## Recipes

**What analytics/trackers actually fire (vs. what a CSP merely permits):** load
the page, read `trace.json`, categorize hosts. CSP `connect-src` lists what's
*allowed*; the trace shows what *ran*.

**Audit a file upload (does it strip EXIF? is storage public?):** set
`CAPTURE_BODIES=1`, attach a file via `page.on('filechooser', fc =>
fc.setFiles(...))` after clicking the upload control. If the app stores to a
public object URL, re-fetch it with `curl -x $HTTPS_PROXY --cacert
$CCR_CA <url>` and diff bytes / read metadata to prove server-side handling.

**Drive a form and watch its calls:** fill fields with `page.fill(...)`, then
inspect which endpoints fire (autocomplete, geocoding, tokenization). Server-side
proxying vs. direct third-party calls is visible in `trace.json`.

## Notes & limits

- **HTTP/1.1 only.** The proxy advertises `http/1.1` in ALPN to keep parsing
  trivial. Fine for tracing; not a general-purpose h2 proxy.
- **One self-signed cert for all hosts.** Works only because Chromium ignores
  cert errors. Never reuse this pattern where cert identity matters.
- **Read-only.** It relays what the browser was going to send anyway and logs
  it. Use it to audit your own testing.
- **Verify the premise first.** If `curl -x $HTTPS_PROXY https://example.com`
  fails too, the problem is egress policy (403/407), not the PQ-ClientHello
  reset — see `/root/.ccr/README.md`, don't reach for this.
- If a future Chromium/egress combo stops resetting, you won't need the proxy at
  all — but it still works as a pure trace capture.
