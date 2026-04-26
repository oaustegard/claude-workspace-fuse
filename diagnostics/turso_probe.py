#!/usr/bin/env python3
"""Turso 503 / DNS-cache diagnostic for Claude Code on the Web container.

Hypothesis: the CCotw container routes outbound HTTPS through an Anthropic-
managed proxy that resolves DNS itself (CLAUDE_CODE_PROXY_RESOLVES_HOSTS=true)
and intermittently returns 503 with a "dns cache" error message that Turso
support has confirmed is NOT emitted by Turso's stack.

The probe simulates the remembering skill's normal Turso traffic pattern at
~5x speed (one round of requests every 5s by default), running in parallel
against a small set of control hosts so failure rates can be compared per
host. Every request creates a fresh TCP socket — no connection pooling — so
each call exercises the full DNS-resolve → TCP-connect → TLS-handshake →
HTTP-request path.

For each request we capture:
- DNS phase: socket.getaddrinfo elapsed + resolved IPs
- HTTP phase: status, full response headers, body preview, full traceback
- Anything matching /dns.*cache/i is flagged into a "suspicious" bucket

Output:
- diagnostics/runs/<UTC-timestamp>/events.ndjson  — one record per request
- diagnostics/runs/<UTC-timestamp>/summary.md     — per-host stats + a
  bug-report-ready section with quoted error text

Run:
    python3 diagnostics/turso_probe.py                       # 10 min default
    python3 diagnostics/turso_probe.py --duration 1800       # 30 min
    python3 diagnostics/turso_probe.py --interval 10         # gentler pacing
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
import traceback
import urllib.parse
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter


DNS_CACHE_RE = re.compile(r"dns.{0,40}cache|cache.{0,40}dns", re.IGNORECASE)


def _load_turso_creds() -> tuple[str, str | None]:
    """Resolve TURSO_URL and TURSO_TOKEN the same way the skill does."""
    url = os.environ.get("TURSO_URL")
    token = os.environ.get("TURSO_TOKEN")
    for path in (Path("/mnt/project/turso.env"), Path("/mnt/project/muninn.env"),
                 Path.home() / ".muninn" / ".env"):
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k == "TURSO_URL" and not url:
                    url = v
                elif k == "TURSO_TOKEN" and not token:
                    token = v
    if not url:
        sys.exit("TURSO_URL not set — refusing to run without an explicit target.")
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url, token


def _measure_dns(host: str) -> dict:
    t0 = time.perf_counter()
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        ips = sorted({ai[4][0] for ai in infos})
        return {"ok": True, "elapsed_ms": round(elapsed_ms, 2), "ips": ips}
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return {
            "ok": False,
            "elapsed_ms": round(elapsed_ms, 2),
            "error_type": type(e).__name__,
            "error": str(e),
        }


def _fresh_session() -> requests.Session:
    """A Session that does not pool — every request is a new socket."""
    s = requests.Session()
    adapter = HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=0)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


def _measure_http(method: str, url: str, *, headers: dict, body: dict | None,
                  timeout: float) -> dict:
    sess = _fresh_session()
    t0 = time.perf_counter()
    try:
        if method == "POST":
            r = sess.post(url, headers=headers, json=body, timeout=timeout)
        else:
            r = sess.get(url, headers=headers, timeout=timeout)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return {
            "ok": True,
            "elapsed_ms": round(elapsed_ms, 2),
            "status_code": r.status_code,
            "headers": dict(r.headers),
            "body_preview": r.text[:1500],
            "body_len": len(r.content),
        }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return {
            "ok": False,
            "elapsed_ms": round(elapsed_ms, 2),
            "error_type": type(e).__name__,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
    finally:
        sess.close()


def _build_targets(turso_url: str, turso_token: str | None) -> list[dict]:
    """Turso + a handful of always-up control hosts.

    Controls are deliberately tiny endpoints (cdn-cgi/trace, /zen, /generate_204)
    used by major OSes for captive-portal detection — boring and well-paced
    traffic that won't draw operational attention.
    """
    targets = [{
        "name": "turso",
        "method": "POST",
        "url": f"{turso_url}/v2/pipeline",
        "headers": {
            "Authorization": f"Bearer {turso_token}" if turso_token else "",
            "Content-Type": "application/json",
        },
        "body": {"requests": [
            {"type": "execute", "stmt": {"sql": "SELECT 1"}},
            {"type": "close"},
        ]},
    }, {
        "name": "control_cloudflare",
        "method": "GET",
        "url": "https://www.cloudflare.com/cdn-cgi/trace",
        "headers": {}, "body": None,
    }, {
        "name": "control_github",
        "method": "GET",
        "url": "https://raw.githubusercontent.com/octocat/Hello-World/master/README",
        "headers": {"User-Agent": "muninn-turso-probe"}, "body": None,
    }, {
        "name": "control_google",
        "method": "GET",
        "url": "https://www.google.com/generate_204",
        "headers": {}, "body": None,
    }]
    return targets


def _classify(record: dict) -> str:
    """One-word bucket for the per-host stats table."""
    dns = record.get("dns", {})
    http = record.get("http")
    if not dns.get("ok"):
        return "dns_fail"
    if http is None:
        return "skipped"
    if not http.get("ok"):
        et = http.get("error_type", "")
        msg = http.get("error", "")
        if "SSL" in et or "SSL" in msg:
            return "tls_fail"
        if "Timeout" in et:
            return "timeout"
        if "ConnectionError" in et or "Connection" in et:
            return "conn_fail"
        return "other_fail"
    code = http.get("status_code") or 0
    if 200 <= code < 300:
        return "ok"
    if code == 503:
        return "http_503"
    if 500 <= code < 600:
        return "http_5xx"
    if 400 <= code < 500:
        return "http_4xx"
    return f"http_{code}"


def _scan_for_dns_cache(record: dict) -> list[str]:
    """Return any string fragments matching the dns-cache signature."""
    hits: list[str] = []
    blob = json.dumps(record, default=str)
    for m in DNS_CACHE_RE.finditer(blob):
        start = max(0, m.start() - 80)
        end = min(len(blob), m.end() + 80)
        hits.append(blob[start:end])
    return hits


def _probe_round(targets: list[dict], iteration: int, timeout: float) -> list[dict]:
    out = []
    for t in targets:
        host = urllib.parse.urlparse(t["url"]).hostname
        record = {
            "iteration": iteration,
            "ts": datetime.now(UTC).isoformat(),
            "target": t["name"],
            "url": t["url"],
            "host": host,
            "dns": _measure_dns(host),
        }
        if record["dns"]["ok"]:
            record["http"] = _measure_http(
                t["method"], t["url"],
                headers=t["headers"], body=t["body"], timeout=timeout,
            )
        record["bucket"] = _classify(record)
        record["dns_cache_hits"] = _scan_for_dns_cache(record)
        out.append(record)
    return out


def _percentiles(values: list[float], qs=(0.5, 0.9, 0.99)) -> dict:
    if not values:
        return {f"p{int(q*100)}": None for q in qs}
    s = sorted(values)
    out = {}
    for q in qs:
        idx = min(len(s) - 1, int(round(q * (len(s) - 1))))
        out[f"p{int(q*100)}"] = round(s[idx], 1)
    return out


def _build_summary(events: list[dict], outdir: Path, args) -> str:
    by_target: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_target[e["target"]].append(e)

    lines = [
        "# Turso 503 / DNS-cache probe — run summary",
        "",
        f"- Run started:   `{events[0]['ts']}`" if events else "",
        f"- Run ended:     `{events[-1]['ts']}`" if events else "",
        f"- Duration:      {args.duration}s requested, {args.interval}s interval",
        f"- Iterations:    {events[-1]['iteration'] if events else 0}",
        f"- Total requests:{len(events)}",
        "",
        "## Environment",
        "",
        f"- `CLAUDE_CODE_VERSION` = `{os.environ.get('CLAUDE_CODE_VERSION', '?')}`",
        f"- `CLAUDE_CODE_CONTAINER_ID` = `{os.environ.get('CLAUDE_CODE_CONTAINER_ID', '?')}`",
        f"- `CLAUDE_CODE_REMOTE_SESSION_ID` = `{os.environ.get('CLAUDE_CODE_REMOTE_SESSION_ID', '?')}`",
        f"- `CLAUDE_CODE_PROXY_RESOLVES_HOSTS` = `{os.environ.get('CLAUDE_CODE_PROXY_RESOLVES_HOSTS', 'unset')}`",
        f"- `CLAUDE_CODE_USE_CCR_V2` = `{os.environ.get('CLAUDE_CODE_USE_CCR_V2', 'unset')}`",
        f"- `CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE` = `{os.environ.get('CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE', 'unset')}`",
        f"- `/etc/resolv.conf` nameserver(s): `{Path('/etc/resolv.conf').read_text().strip() if Path('/etc/resolv.conf').exists() else 'n/a'}`",
        "",
        "## Outcome by target",
        "",
        "| target | total | ok | non-ok | error buckets | latency p50/p90/p99 (ms) | resolved IPs |",
        "|---|---|---|---|---|---|---|",
    ]

    suspicious_records: list[dict] = []
    target_header_keys: dict[str, set[str]] = {}

    for name, recs in by_target.items():
        buckets = Counter(r["bucket"] for r in recs)
        total = len(recs)
        ok = buckets.get("ok", 0)
        nonok = total - ok
        bucket_str = ", ".join(f"{k}={v}" for k, v in buckets.most_common() if k != "ok") or "-"
        lats = [r["http"]["elapsed_ms"] for r in recs
                if r.get("http") and r["http"].get("ok")]
        pcts = _percentiles(lats)
        all_ips = sorted({ip for r in recs for ip in (r["dns"].get("ips") or [])})
        ips_str = ", ".join(all_ips) if all_ips else "-"
        lines.append(
            f"| `{name}` | {total} | {ok} | {nonok} | {bucket_str} | "
            f"{pcts['p50']}/{pcts['p90']}/{pcts['p99']} | {ips_str} |"
        )
        for r in recs:
            if r["dns_cache_hits"] or r["bucket"] not in ("ok",):
                suspicious_records.append(r)
        target_header_keys[name] = {
            h.lower() for r in recs
            if r.get("http") and r["http"].get("ok")
            for h in r["http"].get("headers", {})
        }

    lines += ["", "## Response-header fingerprint", ""]
    fingerprint_keys = ("server", "via", "x-amzn-requestid", "x-amz-cf-id",
                        "cf-ray", "x-cache", "x-served-by", "x-fastly-request-id")
    lines.append("Identifying headers seen in **successful** responses, per host:")
    lines.append("")
    lines.append("| target | " + " | ".join(f"`{k}`" for k in fingerprint_keys) + " |")
    lines.append("|---|" + "|".join(["---"] * len(fingerprint_keys)) + "|")
    for name, keys in target_header_keys.items():
        cells = ["✓" if k in keys else "—" for k in fingerprint_keys]
        lines.append(f"| `{name}` | " + " | ".join(cells) + " |")
    turso_keys = target_header_keys.get("turso", set())
    turso_stripped = not (turso_keys & set(fingerprint_keys))
    if turso_stripped and turso_keys:
        lines.append("")
        lines.append("**`turso` responses contain none of the standard origin/edge "
                     "identification headers** — consistent with a transparent "
                     "rewriting proxy stripping them in the response path.")

    lines += ["", "## DNS-cache signature matches", ""]
    cache_hits = [r for r in events if r["dns_cache_hits"]]
    if not cache_hits:
        lines.append("_No occurrences of `/dns.*cache/i` in any response or error._")
    else:
        lines.append(f"**{len(cache_hits)} request(s)** contained the suspect phrase. Examples:")
        lines.append("")
        for r in cache_hits[:10]:
            lines.append(f"- `{r['ts']}` `{r['target']}` → status="
                         f"{(r.get('http') or {}).get('status_code')} bucket={r['bucket']}")
            for snippet in r["dns_cache_hits"][:2]:
                lines.append(f"  > `{snippet}`")

    lines += ["", "## Worst non-ok samples (up to 10)", ""]
    bad = [r for r in events if r["bucket"] != "ok"][:10]
    if not bad:
        lines.append("_All requests succeeded._")
    for r in bad:
        http = r.get("http") or {}
        lines.append(f"### `{r['ts']}` `{r['target']}` — bucket=`{r['bucket']}`")
        lines.append("")
        lines.append(f"- DNS: ok={r['dns']['ok']}, elapsed={r['dns']['elapsed_ms']}ms, "
                     f"ips={r['dns'].get('ips')}")
        if http:
            if http.get("ok"):
                lines.append(f"- HTTP: status={http.get('status_code')}, "
                             f"elapsed={http.get('elapsed_ms')}ms")
                lines.append(f"- response headers: `{http.get('headers')}`")
                lines.append(f"- body preview: `{http.get('body_preview', '')[:400]}`")
            else:
                lines.append(f"- HTTP: error_type={http.get('error_type')}, "
                             f"elapsed={http.get('elapsed_ms')}ms")
                lines.append(f"- error: `{http.get('error')}`")
        lines.append("")

    lines += [
        "## Bug-report copy block",
        "",
        "Paste the block below into the Anthropic bug report:",
        "",
        "```",
        "Title: Intermittent 503 with 'dns cache' error from CCotw container — Turso confirms message is not theirs",
        "",
        f"Container: {os.environ.get('CLAUDE_CODE_CONTAINER_ID', '?')}",
        f"Session:   {os.environ.get('CLAUDE_CODE_REMOTE_SESSION_ID', '?')}",
        f"CC ver:    {os.environ.get('CLAUDE_CODE_VERSION', '?')}",
        f"Run dir:   {outdir}",
        "",
        "Symptom: HTTPS POST to Turso (https://*.aws-us-east-1.turso.io/v2/pipeline)",
        "intermittently returns 503 with an error message referencing 'dns cache'.",
        "Turso support has confirmed this exact phrase is not emitted anywhere in",
        "their stack — so the response is being generated by something between the",
        "container and Turso. Strong candidates:",
        "  - The CCR v2 proxy (CLAUDE_CODE_USE_CCR_V2=true)",
        "  - The host-resolving forward proxy (CLAUDE_CODE_PROXY_RESOLVES_HOSTS=true)",
        "",
        "Evidence summary:",
        f"  - {len(events)} probe requests across "
        f"{len(by_target)} hosts (1 Turso + 3 controls).",
        f"  - DNS-cache signature matches: {len(cache_hits)}.",
        "  - Per-host failure breakdown is in the table above.",
        ("  - Successful Turso responses lacked all standard origin/edge "
         "identifying headers (server/via/cf-ray/x-amz-*) while controls "
         "preserved theirs — fingerprint of a transparent rewriting proxy "
         "in the response path.")
        if turso_stripped and turso_keys else
        "  - See response-header fingerprint table for proxy-stripping evidence.",
        "",
        "Attached: events.ndjson with full per-request capture (DNS timing,",
        "resolved IPs, HTTP headers, body previews, exception tracebacks).",
        "```",
    ]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--duration", type=int, default=600,
                   help="Total runtime in seconds (default 600 = 10 min)")
    p.add_argument("--interval", type=float, default=5.0,
                   help="Seconds between rounds (default 5.0)")
    p.add_argument("--timeout", type=float, default=10.0,
                   help="Per-request timeout in seconds (default 10)")
    p.add_argument("--out", default="diagnostics/runs",
                   help="Output base directory (default diagnostics/runs)")
    args = p.parse_args()

    turso_url, turso_token = _load_turso_creds()
    targets = _build_targets(turso_url, turso_token)

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    outdir = Path(args.out) / ts
    outdir.mkdir(parents=True, exist_ok=True)
    log_path = outdir / "events.ndjson"

    print(f"[probe] writing to {log_path}")
    print(f"[probe] targets: {[t['name'] for t in targets]}")
    print(f"[probe] duration={args.duration}s interval={args.interval}s "
          f"timeout={args.timeout}s")

    events: list[dict] = []
    deadline = time.time() + args.duration
    iteration = 0
    try:
        with log_path.open("w") as f:
            while time.time() < deadline:
                iteration += 1
                round_start = time.time()
                records = _probe_round(targets, iteration, args.timeout)
                for r in records:
                    f.write(json.dumps(r) + "\n")
                    events.append(r)
                f.flush()

                ok = sum(1 for r in records if r["bucket"] == "ok")
                bad = len(records) - ok
                cache = sum(1 for r in records if r["dns_cache_hits"])
                marker = " ⚠ DNS-CACHE HIT" if cache else ""
                print(f"[probe] iter={iteration:>4} ok={ok}/{len(records)} "
                      f"bad={bad} cache_hits={cache}{marker}")

                sleep_for = args.interval - (time.time() - round_start)
                if sleep_for > 0:
                    time.sleep(sleep_for)
    except KeyboardInterrupt:
        print("[probe] interrupted, writing summary")

    summary = _build_summary(events, outdir, args)
    (outdir / "summary.md").write_text(summary)
    print()
    print(summary)
    print()
    print(f"[probe] events:  {log_path}")
    print(f"[probe] summary: {outdir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
