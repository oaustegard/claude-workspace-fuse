"""bsky_moderation — two-stage Bluesky thread moderation.

Self-contained (only depends on `requests`). Two utilities:

Utility 1 — extract_thread_repliers(post_url, depth=10) -> [{did, handle, name, text}]
    Flattens a thread's replies, deduped by DID (a poster's multiple replies
    are joined with ' ⏎ '). Root author and the authenticated user are excluded.
    Public read; auth optional (only used to exclude self).

Utility 2 — moderate(actions, dry_run=True, max_workers=8) -> [result rows]
    actions: {did: "mute" | "block"}. Executes against the authenticated
    account (BSKY_HANDLE / BSKY_APP_PASSWORD). mute -> app.bsky.graph.muteActor;
    block -> an app.bsky.graph.block record in the user's repo. Runs on a
    bounded thread pool with retry/backoff on transient 429/5xx. dry_run
    defaults True — nothing is written until the caller passes dry_run=False.

Classification (who is muted vs blocked vs left alone) is NOT this module's
job — that reasoning happens between the two utilities.
"""
import os
import time
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

APPVIEW = "https://api.bsky.app/xrpc"   # public reads (public.api.* 403s from containers)
PDS = "https://bsky.social/xrpc"        # authed writes
_TRANSIENT = {429, 500, 502, 503, 504}

_session_cache = {}


# ---------- auth ----------
def _get_session():
    """Create/return a cached session from BSKY_HANDLE / BSKY_APP_PASSWORD.
    Returns None if no credentials are set (reads still work; writes will raise)."""
    global _session_cache
    if _session_cache and time.time() - _session_cache.get("_at", 0) < 7000:
        return _session_cache
    handle = os.environ.get("BSKY_HANDLE", "").strip()
    pw = os.environ.get("BSKY_APP_PASSWORD", "").strip()
    if not handle or not pw:
        return None
    r = requests.post(f"{PDS}/com.atproto.server.createSession",
                      json={"identifier": handle, "password": pw}, timeout=15)
    r.raise_for_status()
    s = r.json()
    s["_at"] = time.time()
    _session_cache = s
    return s


def _resolve_handle(handle):
    r = requests.get(f"{APPVIEW}/com.atproto.identity.resolveHandle",
                     params={"handle": handle}, timeout=15)
    r.raise_for_status()
    return r.json()["did"]


def _ensure_post_uri(post_url_or_uri):
    """Accept an at:// URI or a bsky.app/profile/<h>/post/<rkey> URL."""
    if post_url_or_uri.startswith("at://"):
        return post_url_or_uri
    parts = post_url_or_uri.rstrip("/").split("/")
    rkey = parts[-1]
    handle = parts[parts.index("profile") + 1] if "profile" in parts else parts[-3]
    did = handle if handle.startswith("did:") else _resolve_handle(handle)
    return f"at://{did}/app.bsky.feed.post/{rkey}"


# ---------- Utility 1 ----------
def extract_thread_repliers(post_url, depth=10):
    uri = _ensure_post_uri(post_url)
    r = requests.get(f"{APPVIEW}/app.bsky.feed.getPostThread",
                     params={"uri": uri, "depth": min(depth, 1000), "parentHeight": 0},
                     timeout=30)
    r.raise_for_status()
    thread = r.json().get("thread", {})
    root_did = thread.get("post", {}).get("author", {}).get("did")
    sess = _get_session()
    me = sess.get("did") if sess else None

    acc = {}

    def walk(node):
        p = node.get("post")
        if p:
            a = p.get("author", {})
            did = a.get("did")
            txt = p.get("record", {}).get("text", "").strip()
            if did and did not in (root_did, me):
                e = acc.setdefault(did, {"did": did, "handle": a.get("handle"),
                                         "name": a.get("displayName"), "texts": []})
                if txt:
                    e["texts"].append(txt)
        for rep in node.get("replies", []) or []:
            walk(rep)

    for rep in thread.get("replies", []) or []:
        walk(rep)

    return [{"did": v["did"], "handle": v["handle"], "name": v["name"],
             "text": " \u23ce ".join(v["texts"])} for v in acc.values()]


# ---------- Utility 2 ----------
def _post_with_retry(path, jwt, body, tries=4):
    last = None
    for i in range(tries):
        try:
            r = requests.post(f"{PDS}/{path}",
                              headers={"Authorization": f"Bearer {jwt}"},
                              json=body, timeout=20)
            if r.status_code in _TRANSIENT:
                last = f"{r.status_code} transient"
                time.sleep(0.4 * (i + 1))
                continue
            r.raise_for_status()
            return r.json() if r.content else {}
        except requests.RequestException as e:
            last = str(e)
            time.sleep(0.4 * (i + 1))
    raise RuntimeError(last or "unknown error")


def _do_one(did, act, jwt, my_did):
    try:
        if act == "mute":
            _post_with_retry("app.bsky.graph.muteActor", jwt, {"actor": did})
            res = "muted"
        elif act == "block":
            now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            out = _post_with_retry("com.atproto.repo.createRecord", jwt,
                                   {"repo": my_did, "collection": "app.bsky.graph.block",
                                    "record": {"$type": "app.bsky.graph.block",
                                               "subject": did, "createdAt": now}})
            res = out.get("uri", "blocked")
        else:
            res = f"SKIP_unknown_action:{act}"
        return {"did": did, "action": act, "result": res}
    except Exception as e:
        return {"did": did, "action": act, "result": f"ERROR:{e}"}


def moderate(actions, dry_run=True, max_workers=8):
    """actions: {did: 'mute'|'block'}. Bounded-parallel; retries transient 5xx/429.
    Returns per-did result rows (order not guaranteed)."""
    if dry_run:
        return [{"did": d, "action": a, "result": "DRY_RUN"} for d, a in actions.items()]
    sess = _get_session()
    if not sess or "accessJwt" not in sess:
        raise RuntimeError("not authenticated: set BSKY_HANDLE / BSKY_APP_PASSWORD")
    jwt, my_did = sess["accessJwt"], sess["did"]
    out = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(_do_one, d, a, jwt, my_did) for d, a in actions.items()]
        for f in as_completed(futs):
            out.append(f.result())
    return out
