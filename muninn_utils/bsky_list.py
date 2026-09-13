#!/usr/bin/env python3
"""bsky_list — build and edit Bluesky lists from a source.

The read half of list handling already existed in several places: the
`browsing-bluesky` skill reads a list's posts, `atprotoing` reads the records
straight from a PDS. Nothing here could ever *write* one, so "collect these
accounts into a list" was a task this toolchain could describe and not do.
This module is that half.

Sources it resolves on its own are the two with no existing equivalent -- a
list, and a starter pack -- plus an actor's followers or follows. Anything
else already has a reader: pass the handles or DIDs it produced as a literal
sequence and skip resolution entirely.

    from muninn_utils.bsky_list import build_list
    build_list("Cyclists", "starterpack:https://bsky.app/starter-pack/...")
    build_list("Mentioned", ["alice.example", "did:plc:..."])

IDENTITY. Writes go to Muninn's repo by default, from MUNINN_BSKY_HANDLE /
MUNINN_BSKY_APP_PASSWORD. Oskar's credentials also sit in the environment as
the unprefixed BSKY_HANDLE / BSKY_APP_PASSWORD, and `browsing-bluesky` picks
those up silently -- which is how an ostensibly read-only skill came to hold
an app password with write scope on his account. A write tool must not repeat
that by accident, so writing as Oskar takes an explicit `as_oskar=True`.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request

APPVIEW = "https://public.api.bsky.app/xrpc"
PDS_DEFAULT = "https://bsky.social"

#: The three list purposes atproto defines. A curatelist feeds a custom feed,
#: a modlist drives mutes and blocks, a referencelist backs a starter pack.
#: Naming the wrong one silently produces a list the UI will not show where
#: the caller expects it.
PURPOSES = {
    "curatelist": "app.bsky.graph.defs#curatelist",
    "modlist": "app.bsky.graph.defs#modlist",
    "referencelist": "app.bsky.graph.defs#referencelist",
}

#: applyWrites caps a batch at 200 operations. Chunking at 100 leaves room
#: for the caller to be wrong about that without a 400 mid-import.
BATCH = 100

#: A single connection reset aborted a 77-member import mid-run on the first
#: live test. Every call here is idempotent-by-construction on retry (reads
#: are reads; a write that never reached the PDS created nothing), so retrying
#: transport failures is safe and not retrying them is the bug.
TRIES = 3


class ListError(Exception):
    """A source could not be resolved or a write was rejected."""


# ── transport ──────────────────────────────────────────────────────────

def _send(req, label, timeout=30):
    """One request, retried on transport failure and 429/5xx. 4xx is final."""
    import time
    last = None
    for attempt in range(TRIES):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode("utf8", "replace")
            if 400 <= e.code < 500 and e.code != 429:
                raise ListError(f"{label} rejected (HTTP {e.code}): {detail}") from e
            last = ListError(f"{label} failed (HTTP {e.code}): {detail}")
        except (urllib.error.URLError, OSError) as e:
            last = ListError(f"{label} unreachable: {getattr(e, 'reason', e)}")
        if attempt < TRIES - 1:
            time.sleep(1.5 * (attempt + 1))
    raise last


def _get(url, params=None, timeout=30):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    return _send(urllib.request.Request(
        url, headers={"User-Agent": "muninn-bsky-list"}),
        urllib.parse.urlsplit(url).path, timeout)


def _post(path, body, auth, timeout=30):
    return _send(urllib.request.Request(
        f"{auth['pds']}/xrpc/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {auth['access_jwt']}",
                 "Content-Type": "application/json",
                 "User-Agent": "muninn-bsky-list"}), path, timeout)


def _now():
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# ── identity ───────────────────────────────────────────────────────────

def auth_for(as_oskar=False, pds=None):
    """A session for whoever should own the write.

    Defaults to Muninn. `as_oskar=True` is the only way to reach the
    unprefixed BSKY_* pair, so a list never lands in his repo because a
    variable happened to be set.
    """
    prefix = "" if as_oskar else "MUNINN_"
    handle = os.environ.get(f"{prefix}BSKY_HANDLE", "").strip()
    password = os.environ.get(f"{prefix}BSKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        who = "BSKY_HANDLE / BSKY_APP_PASSWORD" if as_oskar else \
              "MUNINN_BSKY_HANDLE / MUNINN_BSKY_APP_PASSWORD"
        raise ListError(f"set {who} in the environment")
    pds = (pds or os.environ.get("BSKY_PDS") or PDS_DEFAULT).rstrip("/")
    # Through _send like everything else: a createSession lost to a
    # connection reset is the same transient failure as any other call, and
    # it would otherwise abort the whole import before it started.
    s = _send(urllib.request.Request(
        f"{pds}/xrpc/com.atproto.server.createSession",
        data=json.dumps({"identifier": handle, "password": password}).encode(),
        method="POST", headers={"Content-Type": "application/json"}),
        "com.atproto.server.createSession")
    return {"access_jwt": s["accessJwt"], "did": s["did"],
            "handle": s["handle"], "pds": pds}


def resolve_actor(actor):
    """handle|DID -> DID. A DID passes through without a round trip."""
    if actor.startswith("did:"):
        return actor
    return _get(f"{APPVIEW}/com.atproto.identity.resolveHandle",
                {"handle": actor})["did"]


# ── source resolution (unauthenticated reads) ──────────────────────────

def _paged(path, params, key, limit=None, page=100):
    out, cursor = [], None
    while True:
        p = dict(params, limit=min(page, limit - len(out)) if limit else page)
        if cursor:
            p["cursor"] = cursor
        r = _get(f"{APPVIEW}/{path}", p)
        out += r.get(key, [])
        cursor = r.get("cursor")
        if not cursor or not r.get(key) or (limit and len(out) >= limit):
            return out[:limit] if limit else out


def parse_source(source):
    """`<kind>:<ref>`, a bsky.app URL, an at:// URI, or a sequence of actors.

    Returns `(kind, ref)`. Bare strings are sniffed: a starter-pack URL and a
    list URL differ only by a path segment, and getting that backwards
    silently builds the wrong list.
    """
    if not isinstance(source, str):
        return "actors", list(source)
    for kind in ("list", "starterpack", "followers", "follows", "actors"):
        if source.startswith(f"{kind}:") and not source.startswith(f"{kind}://"):
            ref = source[len(kind) + 1:]
            return kind, ([a.strip() for a in ref.split(",")] if kind == "actors"
                          else ref)
    if "/starter-pack/" in source or "app.bsky.graph.starterpack" in source:
        return "starterpack", source
    if "/lists/" in source or "app.bsky.graph.list/" in source:
        return "list", source
    raise ListError(
        f"cannot tell what {source!r} is — prefix it "
        "(list:/starterpack:/followers:/follows:/actors:) or pass a sequence")


def _to_at_uri(ref, collection):
    """A bsky.app URL or an at:// URI -> an at:// URI for `collection`."""
    if ref.startswith("at://"):
        return ref
    parts = [p for p in urllib.parse.urlsplit(ref).path.split("/") if p]
    # /profile/<actor>/lists/<rkey>  or  /starter-pack/<actor>/<rkey>
    if "profile" in parts:
        actor, rkey = parts[parts.index("profile") + 1], parts[-1]
    elif "starter-pack" in parts:
        actor, rkey = parts[parts.index("starter-pack") + 1], parts[-1]
    else:
        raise ListError(f"no actor/rkey in {ref!r}")
    return f"at://{resolve_actor(actor)}/{collection}/{rkey}"


def resolve_source(source, limit=None):
    """A source -> `{kind, ref, actors: [{did, handle}]}`."""
    kind, ref = parse_source(source)
    if kind == "actors":
        return {"kind": kind, "ref": ref,
                "actors": [{"did": resolve_actor(a), "handle": a} for a in ref]}
    if kind in ("followers", "follows"):
        path = ("app.bsky.graph.getFollowers" if kind == "followers"
                else "app.bsky.graph.getFollows")
        key = "followers" if kind == "followers" else "follows"
        rows = _paged(path, {"actor": ref}, key, limit)
        return {"kind": kind, "ref": ref,
                "actors": [{"did": a["did"], "handle": a["handle"]} for a in rows]}
    if kind == "starterpack":
        uri = _to_at_uri(ref, "app.bsky.graph.starterpack")
        pack = _get(f"{APPVIEW}/app.bsky.graph.getStarterPack",
                    {"starterPack": uri})["starterPack"]
        # The pack itself carries only a 12-account sample; the real
        # membership is the referencelist it points at.
        backing = pack["record"].get("list") or pack.get("list", {}).get("uri")
        if not backing:
            raise ListError(f"starter pack {uri} references no list")
        out = resolve_source(f"list:{backing}", limit)
        return {"kind": kind, "ref": uri, "actors": out["actors"]}
    uri = _to_at_uri(ref, "app.bsky.graph.list")
    rows = _paged("app.bsky.graph.getList", {"list": uri}, "items", limit)
    return {"kind": "list", "ref": uri,
            "actors": [{"did": i["subject"]["did"],
                        "handle": i["subject"]["handle"]} for i in rows]}


def list_members(list_uri, limit=None):
    """Everyone on a list per the AppView, with the listitem URI behind each.

    The AppView is the only route to a list you do not own, and it lags
    writes by seconds. For a list in your own repo use `own_members`, which
    reads the repo: after removing two members here, this still returned all
    77 for several seconds, and deleting from that stale answer made the PDS
    return a 500 on records that no longer existed.
    """
    rows = _paged("app.bsky.graph.getList", {"list": list_uri}, "items", limit)
    return [{"did": i["subject"]["did"], "handle": i["subject"]["handle"],
             "item_uri": i["uri"]} for i in rows]


def own_members(list_uri, auth):
    """The listitems for `list_uri` as the owning repo actually holds them.

    Authoritative and immediate — no index sits between this and the record.
    Every write path below reads through here for that reason.
    """
    out, cursor = [], None
    while True:
        p = {"repo": auth["did"], "collection": "app.bsky.graph.listitem",
             "limit": 100}
        if cursor:
            p["cursor"] = cursor
        page = _get(f"{auth['pds']}/xrpc/com.atproto.repo.listRecords", p)
        out += [{"did": r["value"]["subject"], "item_uri": r["uri"]}
                for r in page["records"] if r["value"].get("list") == list_uri]
        cursor = page.get("cursor")
        if not cursor or not page["records"]:
            return out


# ── writes ─────────────────────────────────────────────────────────────

def create_list(name, description="", purpose="curatelist", auth=None,
                as_oskar=False):
    """Create an empty list. Returns `{uri, cid, url, owner}`."""
    if purpose not in PURPOSES:
        raise ListError(f"purpose must be one of {sorted(PURPOSES)}, got {purpose!r}")
    auth = auth or auth_for(as_oskar)
    r = _post("com.atproto.repo.createRecord", {
        "repo": auth["did"], "collection": "app.bsky.graph.list",
        "record": {"$type": "app.bsky.graph.list", "purpose": PURPOSES[purpose],
                   "name": name, "description": description,
                   "createdAt": _now()}}, auth)
    rkey = r["uri"].rsplit("/", 1)[1]
    return {"uri": r["uri"], "cid": r["cid"], "owner": auth["handle"],
            "url": f"https://bsky.app/profile/{auth['handle']}/lists/{rkey}"}


def add_members(list_uri, actors, auth=None, as_oskar=False, skip_existing=True):
    """Add accounts to a list. Returns `{added, skipped, total}`.

    `skip_existing` reads the owning repo first and drops anyone already on
    the list — atproto will happily store a second listitem for the same
    subject, and the duplicate shows up as a repeated row in every client.
    """
    auth = auth or auth_for(as_oskar)
    dids, seen = [], set()
    for a in actors:
        did = a["did"] if isinstance(a, dict) else resolve_actor(a)
        if did not in seen:
            seen.add(did)
            dids.append(did)
    skipped = 0
    if skip_existing:
        already = {m["did"] for m in own_members(list_uri, auth)}
        before = len(dids)
        dids = [d for d in dids if d not in already]
        skipped = before - len(dids)
    for i in range(0, len(dids), BATCH):
        _post("com.atproto.repo.applyWrites", {
            "repo": auth["did"],
            "writes": [{"$type": "com.atproto.repo.applyWrites#create",
                        "collection": "app.bsky.graph.listitem",
                        "value": {"$type": "app.bsky.graph.listitem",
                                  "subject": d, "list": list_uri,
                                  "createdAt": _now()}}
                       for d in dids[i:i + BATCH]]}, auth)
    return {"added": len(dids), "skipped": skipped, "total": len(seen)}


def remove_members(list_uri, actors, auth=None, as_oskar=False):
    """Drop accounts from a list. Returns `{removed, not_found}`."""
    auth = auth or auth_for(as_oskar)
    wanted = {a["did"] if isinstance(a, dict) else resolve_actor(a) for a in actors}
    items = [m for m in own_members(list_uri, auth) if m["did"] in wanted]
    for i in range(0, len(items), BATCH):
        _post("com.atproto.repo.applyWrites", {
            "repo": auth["did"],
            "writes": [{"$type": "com.atproto.repo.applyWrites#delete",
                        "collection": "app.bsky.graph.listitem",
                        "rkey": m["item_uri"].rsplit("/", 1)[1]}
                       for m in items[i:i + BATCH]]}, auth)
    return {"removed": len(items), "not_found": len(wanted) - len(items)}


def delete_list(list_uri, auth=None, as_oskar=False, with_members=True):
    """Delete a list, and by default its listitems too.

    Deleting only the list record leaves every listitem orphaned in the repo,
    pointing at a URI that no longer resolves. They are invisible in the UI
    and count against the repo forever, so removing them is the default.
    """
    auth = auth or auth_for(as_oskar)
    removed = 0
    if with_members:
        removed = remove_members(
            list_uri, own_members(list_uri, auth), auth)["removed"]
    _post("com.atproto.repo.deleteRecord", {
        "repo": auth["did"], "collection": "app.bsky.graph.list",
        "rkey": list_uri.rsplit("/", 1)[1]}, auth)
    return {"deleted": list_uri, "members_removed": removed}


def build_list(name, source, description="", purpose="curatelist", limit=None,
               auth=None, as_oskar=False, into=None):
    """Resolve a source and put its accounts on a list, new or existing.

    The one call that does the whole job: `build_list("Cyclists",
    "starterpack:<url>")`. `into` targets an existing list instead of
    creating one.
    """
    auth = auth or auth_for(as_oskar)
    resolved = resolve_source(source, limit)
    if into:
        target = {"uri": into, "owner": auth["handle"],
                  "url": f"https://bsky.app/profile/{auth['handle']}"
                         f"/lists/{into.rsplit('/', 1)[1]}"}
    else:
        target = create_list(name, description, purpose, auth)
    # A list created a moment ago has no members, and the AppView has not
    # indexed it yet either — the dedupe read would be a round trip that can
    # only fail or return nothing.
    counts = add_members(target["uri"], resolved["actors"], auth,
                         skip_existing=bool(into))
    return {**target, "source": {"kind": resolved["kind"], "ref": resolved["ref"]},
            **counts}


# ── cli ────────────────────────────────────────────────────────────────
# Same envelope contract as bsky_card: one JSON object on stdout, always,
# and an {"error": {code, message}} shape when something fails.

def _envelope(code, message):
    return {"error": {"code": code, "message": message}}


def _action_whoami(_payload):
    """Report which account a write would land in, before one does."""
    auth = auth_for(bool(_payload.get("as_oskar")))
    return {"handle": auth["handle"], "did": auth["did"], "pds": auth["pds"]}


def _action_resolve_source(payload):
    """Preview a source without writing anything. {source, limit?}"""
    if not payload.get("source"):
        raise ListError("resolve-source requires 'source'")
    r = resolve_source(payload["source"], payload.get("limit"))
    return {"kind": r["kind"], "ref": r["ref"], "count": len(r["actors"]),
            "actors": r["actors"]}


def _action_build_list(payload):
    """{name, source, description?, purpose?, limit?, into?, as_oskar?}"""
    if not payload.get("source") or not (payload.get("name") or payload.get("into")):
        raise ListError("build-list requires 'source' and either 'name' or 'into'")
    return build_list(payload.get("name", ""), payload["source"],
                      payload.get("description", ""),
                      payload.get("purpose", "curatelist"),
                      payload.get("limit"), None,
                      bool(payload.get("as_oskar")), payload.get("into"))


def _action_list_members(payload):
    """{list, own?} — own reads the repo, otherwise the AppView."""
    if not payload.get("list"):
        raise ListError("list-members requires 'list'")
    if payload.get("own"):
        auth = auth_for(bool(payload.get("as_oskar")))
        members = own_members(payload["list"], auth)
    else:
        members = list_members(payload["list"], payload.get("limit"))
    return {"list": payload["list"], "count": len(members), "members": members}


def _action_remove_members(payload):
    """{list, actors: [...]}"""
    if not payload.get("list") or not payload.get("actors"):
        raise ListError("remove-members requires 'list' and 'actors'")
    return remove_members(payload["list"], payload["actors"],
                          as_oskar=bool(payload.get("as_oskar")))


def _action_delete_list(payload):
    """{list, with_members?} — removes the listitems too unless told not to."""
    if not payload.get("list"):
        raise ListError("delete-list requires 'list'")
    return delete_list(payload["list"], as_oskar=bool(payload.get("as_oskar")),
                       with_members=payload.get("with_members", True))


ACTIONS = {
    "whoami": _action_whoami,
    "resolve-source": _action_resolve_source,
    "build-list": _action_build_list,
    "list-members": _action_list_members,
    "remove-members": _action_remove_members,
    "delete-list": _action_delete_list,
}


def _main(argv):
    import contextlib
    import sys

    real_stdout = sys.stdout

    def emit(obj):
        real_stdout.write(json.dumps(obj) + "\n")
        real_stdout.flush()

    usage = ("usage: python -m muninn_utils.bsky_list <" + "|".join(ACTIONS)
             + ">  (each reads a JSON object from stdin)")
    if not argv or argv[0] in ("-h", "--help"):
        emit(_envelope("error", usage))
        return 2
    fn = ACTIONS.get(argv[0])
    if fn is None:
        emit(_envelope("error", f"unknown action {argv[0]!r}. {usage}"))
        return 2
    try:
        raw = sys.stdin.read().strip()
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        emit(_envelope("error", f"invalid JSON on stdin: {e}"))
        return 1
    try:
        with contextlib.redirect_stdout(sys.stderr):
            result = fn(payload)
    except ListError as e:
        emit(_envelope("error", str(e)))
        return 1
    except Exception as e:  # noqa: BLE001 — last-resort envelope; never bare-crash
        emit(_envelope("error", f"{type(e).__name__}: {e}"))
        return 1
    emit(result)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
