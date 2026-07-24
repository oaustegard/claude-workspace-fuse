"""
whtwnd.py - WhiteWind blog publishing via ATProto

Post/update/delete/list blog entries on whtwnd.com.
Upload images as ATProto blobs.

Auth: com.atproto.server.createSession (same as margin/bsky).
Write: com.atproto.repo.createRecord to user's PDS.
Collection: com.whtwnd.blog.entry

CRITICAL: Image URL pattern is https://{pds}/xrpc/com.atproto.sync.getBlob?did={did}&cid={cid}
NOT cdn.bsky.app (which returns 500 for non-Bluesky records).
Blobs MUST be in record's blobs array or PDS garbage-collects them.

Usage:
    from muninn_utils.whtwnd import whtwnd_auth, whtwnd_post, whtwnd_upload_image

    auth = whtwnd_auth('austegard.com', 'xxxx-xxxx-xxxx-xxxx')
    img = whtwnd_upload_image('header.png', auth=auth)
    content = f"# Title\\n\\n{img['markdown']}\\n\\nBody..."
    result = whtwnd_post(content, "My Post", auth=auth, blobs=[img['blob_metadata']])
    print(result['post_url'])
"""

import json
import urllib.request
import urllib.error
import os
import mimetypes
from datetime import datetime, timezone


COLLECTION = "com.whtwnd.blog.entry"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def whtwnd_auth(handle: str = None, app_password: str = None) -> dict:
    """
    Authenticate via com.atproto.server.createSession.
    Returns dict with access_jwt, did, handle, pds (hostname).
    Auto-discovers credentials from BSKY_HANDLE/BSKY_APP_PASSWORD env vars.
    """
    handle = handle or os.environ.get("BSKY_HANDLE")
    app_password = app_password or os.environ.get("BSKY_APP_PASSWORD")
    if not handle or not app_password:
        raise ValueError("Provide handle/app_password or set BSKY_HANDLE/BSKY_APP_PASSWORD")

    req = urllib.request.Request(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        data=json.dumps({"identifier": handle, "password": app_password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    session = json.loads(urllib.request.urlopen(req).read())
    access_jwt = session["accessJwt"]
    did = session["did"]
    pds_url = next(
        s["serviceEndpoint"]
        for s in session["didDoc"]["service"]
        if s["id"] == "#atproto_pds"
    )
    pds = pds_url.replace("https://", "")

    return {
        "access_jwt": access_jwt,
        "did": did,
        "handle": session.get("handle", handle),
        "pds": pds,
    }


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def whtwnd_post(
    content: str,
    title: str,
    *,
    visibility: str = "public",
    created_at: str = None,
    blobs: list = None,
    auth: dict = None,
) -> dict:
    """
    Create a new blog post on WhiteWind.

    Args:
        content: Markdown content
        title: Post title
        visibility: 'public' or 'author'
        created_at: ISO timestamp (default: now)
        blobs: List of blob metadata dicts [{"blobref": blob_obj, "name": "file.png"}]
        auth: Dict from whtwnd_auth()

    Returns: dict with rkey, uri, cid, post_url
    """
    if not auth:
        raise ValueError("auth required - call whtwnd_auth() first")

    now = created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    record = {
        "$type": COLLECTION,
        "content": content,
        "title": title,
        "createdAt": now,
        "visibility": visibility,
    }

    if blobs:
        record["blobs"] = blobs

    payload = {
        "repo": auth["did"],
        "collection": COLLECTION,
        "record": record,
    }

    req = urllib.request.Request(
        f"https://{auth['pds']}/xrpc/com.atproto.repo.createRecord",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth['access_jwt']}",
        },
        method="POST",
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    rkey = resp["uri"].split("/")[-1]

    return {
        "rkey": rkey,
        "uri": resp["uri"],
        "cid": resp.get("cid"),
        "post_url": f"https://whtwnd.com/{auth['handle']}/{rkey}",
    }


def whtwnd_update(
    rkey: str,
    content: str,
    title: str,
    *,
    visibility: str = "public",
    created_at: str = None,
    blobs: list = None,
    auth: dict = None,
) -> dict:
    """Update an existing blog post."""
    if not auth:
        raise ValueError("auth required")

    now = created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    record = {
        "$type": COLLECTION,
        "content": content,
        "title": title,
        "createdAt": now,
        "visibility": visibility,
    }

    if blobs:
        record["blobs"] = blobs

    payload = {
        "repo": auth["did"],
        "collection": COLLECTION,
        "rkey": rkey,
        "record": record,
    }

    req = urllib.request.Request(
        f"https://{auth['pds']}/xrpc/com.atproto.repo.putRecord",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth['access_jwt']}",
        },
        method="POST",
    )
    resp = json.loads(urllib.request.urlopen(req).read())

    return {
        "rkey": rkey,
        "uri": resp["uri"],
        "cid": resp.get("cid"),
        "post_url": f"https://whtwnd.com/{auth['handle']}/{rkey}",
    }


def whtwnd_delete(rkey: str, *, auth: dict = None) -> bool:
    """Delete a blog post."""
    if not auth:
        raise ValueError("auth required")

    payload = {
        "repo": auth["did"],
        "collection": COLLECTION,
        "rkey": rkey,
    }

    req = urllib.request.Request(
        f"https://{auth['pds']}/xrpc/com.atproto.repo.deleteRecord",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth['access_jwt']}",
        },
        method="POST",
    )
    urllib.request.urlopen(req)
    return True


def whtwnd_list(
    did: str = None,
    handle: str = None,
    limit: int = 20,
    *,
    auth: dict = None,
) -> list:
    """List blog entries. Uses auth credentials if no did/handle provided."""
    if not did and auth:
        did = auth["did"]
    if not did and not handle:
        raise ValueError("Provide did, handle, or auth")

    repo = did or handle
    url = (
        f"https://bsky.social/xrpc/com.atproto.repo.listRecords"
        f"?repo={repo}&collection={COLLECTION}&limit={limit}"
    )

    req = urllib.request.Request(url)
    resp = json.loads(urllib.request.urlopen(req).read())

    posts = []
    for r in resp.get("records", []):
        v = r["value"]
        rkey = r["uri"].split("/")[-1]
        h = handle or (auth["handle"] if auth else repo)
        posts.append({
            "rkey": rkey,
            "uri": r["uri"],
            "title": v.get("title", "(untitled)"),
            "created_at": v.get("createdAt", ""),
            "visibility": v.get("visibility", "public"),
            "content_length": len(v.get("content", "")),
            "post_url": f"https://whtwnd.com/{h}/{rkey}",
        })

    return posts


# ---------------------------------------------------------------------------
# Image upload
# ---------------------------------------------------------------------------

def whtwnd_upload_image(image_path: str, *, auth: dict = None) -> dict:
    """
    Upload an image as an ATProto blob.

    Returns dict with:
        blob_obj: The blob reference object for use in records
        url: Direct URL to the blob (via PDS getBlob)
        markdown: Ready-to-use markdown image tag
        blob_metadata: Dict for the blobs[] array {"blobref": blob_obj, "name": filename}
    """
    if not auth:
        raise ValueError("auth required")

    mime_type = mimetypes.guess_type(image_path)[0] or "image/png"
    filename = os.path.basename(image_path)

    with open(image_path, "rb") as f:
        image_data = f.read()

    req = urllib.request.Request(
        f"https://{auth['pds']}/xrpc/com.atproto.repo.uploadBlob",
        data=image_data,
        headers={
            "Content-Type": mime_type,
            "Authorization": f"Bearer {auth['access_jwt']}",
        },
        method="POST",
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    blob_obj = resp["blob"]
    cid = blob_obj["ref"]["$link"]

    # CRITICAL: Use PDS getBlob URL, NOT cdn.bsky.app
    blob_url = (
        f"https://{auth['pds']}/xrpc/com.atproto.sync.getBlob"
        f"?did={auth['did']}&cid={cid}"
    )

    return {
        "blob_obj": blob_obj,
        "url": blob_url,
        "markdown": f"![{filename}]({blob_url})",
        "blob_metadata": {"blobref": blob_obj, "name": filename},
    }
