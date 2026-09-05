"""strava — pull a Strava activity in one import, no OAuth hand-rolling.

The friction this kills (Oskar, 2026-06-14: "My GOD you struggled"): every
session re-derived the refresh→fetch dance, fished the token out of a memory
body via FTS, and guessed config_set categories. Here the token lives at a
stable config key and the dance is one call.

    from muninn_utils import strava
    ride = strava.latest()            # newest activity, detailed + analyzed
    ride = strava.latest(kind="Ride") # newest Ride specifically
    act  = strava.activity(123456)    # a specific activity id
    acts = strava.recent(n=10)        # list summaries (no detail/streams)

Each detailed return includes ['analysis'] with cardiac drift, Pw:HR
decoupling, HR-zone distribution, and thirds — the coaching read inputs.

Auth contract:
  - STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET from env (project *.env).
  - Token JSON at config key 'strava-oauth-token' (category 'ops'):
        {"access_token","refresh_token","expires_at"}
  - On load, if access_token is expired (or within 300s), auto-refresh and
    write the rotated token back to the SAME config key. No memory-FTS, no
    category guessing.
  - First-run fallback: if the config key is absent, FTS-recall a legacy
    'STRAVA_OAUTH_TOKENS {...}' memory once, then migrate it to config.
"""
import os
import json
import time
import urllib.request
import urllib.parse

TOKEN_KEY = "strava-oauth-token"
API = "https://www.strava.com/api/v3"
OAUTH = "https://www.strava.com/oauth/token"
_REFRESH_SKEW = 300  # refresh if within 5 min of expiry


# ── token storage (config-backed, single source of truth) ──────────────────

def _load_token():
    from scripts import config_get
    raw = config_get(TOKEN_KEY)
    if raw:
        return json.loads(raw)
    # one-time migration from legacy memory body
    from scripts import recall
    for r in recall(query="STRAVA_OAUTH_TOKENS refresh_token access_token", n=6):
        b = r.get("summary", "") or r.get("body", "")
        if "refresh_token" in b:
            tok = json.loads(b[b.index("{"):b.rindex("}") + 1])
            _save_token(tok)
            return tok
    raise RuntimeError(
        f"No Strava token at config key '{TOKEN_KEY}' and no legacy memory "
        "found. Re-run the OAuth grant to seed it.")


def _save_token(tok):
    from scripts import config_set
    config_set(TOKEN_KEY, json.dumps(tok), "ops")


def _refresh(tok):
    cid = os.environ["STRAVA_CLIENT_ID"]
    csec = os.environ["STRAVA_CLIENT_SECRET"]
    data = urllib.parse.urlencode({
        "client_id": cid, "client_secret": csec,
        "grant_type": "refresh_token",
        "refresh_token": tok["refresh_token"],
    }).encode()
    resp = _http(OAUTH, data=data, method="POST")
    new = {k: resp[k] for k in ("access_token", "refresh_token", "expires_at")}
    _save_token(new)
    return new


def access_token():
    """Return a valid bearer token, refreshing + persisting if needed."""
    tok = _load_token()
    if tok.get("expires_at", 0) - time.time() < _REFRESH_SKEW:
        tok = _refresh(tok)
    return tok["access_token"]


# ── http (with one proxy-503 retry; see proxy-503-retry-pattern) ───────────

def _http(url, data=None, method="GET", token=None, _tries=3):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    last = None
    for attempt in range(_tries):
        try:
            req = urllib.request.Request(url, data=data, method=method, headers=headers)
            with urllib.request.urlopen(req) as r:
                return json.loads(r.read())
        except Exception as e:  # transient proxy/DNS or 5xx
            last = e
            time.sleep(0.5 * (attempt + 1))
    raise last


def _get(path, token):
    return _http(f"{API}{path}", token=token)


# ── analysis ───────────────────────────────────────────────────────────────

def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else 0.0


def analyze_streams(streams):
    """Cardiac drift, Pw:HR decoupling, HR-zone split, thirds. Inputs are
    raw Strava stream dicts (key_by_type=true)."""
    hr = streams.get("heartrate", {}).get("data", []) or []
    w = streams.get("watts", {}).get("data", []) or []
    n = len(hr)
    out = {"samples": n}
    if n == 0:
        return out

    def seg(lst, a, b):
        return _mean(lst[a:b]) if lst else 0.0

    thirds = []
    for i in range(3):
        a, b = i * n // 3, (i + 1) * n // 3
        h, p = seg(hr, a, b), seg(w, a, b)
        thirds.append({"hr": round(h), "watts": round(p),
                       "w_per_hr": round(p / h, 2) if h else None})
    out["thirds"] = thirds

    half = n // 2
    if w:
        h1, h2 = seg(hr, 0, half), seg(hr, half, n)
        p1, p2 = seg(w, 0, half), seg(w, half, n)
        if h1 and h2 and p1:
            r1, r2 = p1 / h1, p2 / h2
            out["decoupling_pct"] = round((r1 - r2) / r1 * 100, 1)

    bands = [("Z1_<120", 0, 120), ("Z2_120-140", 120, 140),
             ("Z3_140-155", 140, 155), ("Z4_155-167", 155, 167),
             ("Z5_167+", 167, 10**9)]
    zones, tot = {}, 0
    for name, lo, hi in bands:
        c = sum(1 for x in hr if x is not None and lo <= x < hi)
        zones[name] = c
        tot += c
    out["hr_zone_pct"] = {k: round(v / tot * 100) for k, v in zones.items()} if tot else {}
    return out


# ── public API ─────────────────────────────────────────────────────────────

def recent(n=5):
    """List recent activity summaries (no detail, no streams)."""
    tok = access_token()
    return _get(f"/athlete/activities?per_page={n}", tok)


def activity(activity_id, with_streams=True):
    """Fetch one activity, detailed; attach ['analysis'] from streams."""
    tok = access_token()
    a = _get(f"/activities/{activity_id}?include_all_efforts=false", tok)
    if with_streams:
        s = _get(f"/activities/{activity_id}/streams"
                 "?keys=heartrate,watts,velocity_smooth,time,distance&key_by_type=true", tok)
        a["analysis"] = analyze_streams(s)
    return a


def latest(kind=None, with_streams=True):
    """Newest activity (optionally filtered by type, e.g. 'Ride'), detailed."""
    for s in recent(n=15):
        if kind is None or s.get("type") == kind:
            return activity(s["id"], with_streams=with_streams)
    raise RuntimeError(f"No recent activity of type={kind!r} found.")


if __name__ == "__main__":
    import sys
    kind = sys.argv[1] if len(sys.argv) > 1 else None
    r = latest(kind=kind)
    mi = r["distance"] / 1609.34
    print(f"{r['name']} | {r['start_date_local']} | {mi:.1f}mi | "
          f"NP{r.get('weighted_average_watts','?')}W avg{r.get('average_watts','?')}W | "
          f"HR{r.get('average_heartrate','?')}")
    print(json.dumps(r.get("analysis", {}), indent=2))
