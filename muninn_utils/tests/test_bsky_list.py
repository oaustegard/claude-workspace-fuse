"""Offline tests for bsky_list.

`_send` is stubbed throughout, so nothing here reaches bsky.social or the
AppView. What is under test is the shaping: which surface each path reads,
what the identity default is, and how the two registries stay covered.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from muninn_utils import bsky_list as bl  # noqa: E402
from muninn_utils.bsky_list import ACTIONS, PURPOSES  # noqa: E402

AUTH = {"access_jwt": "jwt", "did": "did:plc:me", "handle": "me.example",
        "pds": "https://pds.example"}
LIST = "at://did:plc:me/app.bsky.graph.list/L1"


@pytest.fixture
def net(monkeypatch):
    """Stub `_send` with a url-tail -> payload table; record every request."""
    table: dict[str, object] = {}
    sent: list[dict] = []

    def fake(req, label, timeout=30):
        body = json.loads(req.data.decode()) if req.data else None
        sent.append({"url": req.full_url, "label": label, "body": body})
        base = req.full_url.split("?")[0]
        hits = [f for f in table if base.endswith(f)]
        if not hits:
            raise AssertionError(f"unstubbed request: {req.full_url}")
        payload = table[hits[0]]
        return payload(body) if callable(payload) else payload

    monkeypatch.setattr(bl, "_send", fake)
    return table, sent


# ── identity ───────────────────────────────────────────────────────────

def test_auth_defaults_to_muninn_and_reaches_oskar_only_on_request(net, monkeypatch):
    """invariant: auth_for() reads MUNINN_BSKY_*; only as_oskar=True reads BSKY_*.

    refuted: swapping the prefix so `as_oskar` selects "" the other way round
    -> this test alone went red, with auth_for() authenticating as oskar.
    """
    table, sent = net
    monkeypatch.setenv("MUNINN_BSKY_HANDLE", "muninn.example")
    monkeypatch.setenv("MUNINN_BSKY_APP_PASSWORD", "m-pw")
    monkeypatch.setenv("BSKY_HANDLE", "oskar.example")
    monkeypatch.setenv("BSKY_APP_PASSWORD", "o-pw")
    table["createSession"] = lambda body: {
        "accessJwt": "j", "did": "did:plc:x", "handle": body["identifier"]}

    assert bl.auth_for()["handle"] == "muninn.example"
    assert bl.auth_for(as_oskar=True)["handle"] == "oskar.example"


def test_missing_muninn_credentials_do_not_fall_back_to_oskar(monkeypatch):
    """invariant: an unset MUNINN_* pair raises rather than silently using BSKY_*.

    This is the `browsing-bluesky` defect the module exists not to repeat:
    a tool that reads whatever credential happens to be set writes to
    whichever account happens to be configured.

    refuted: replacing the raise with a fallback to the unprefixed pair ->
    this test alone went red, auth_for() returning oskar.example.
    """
    monkeypatch.delenv("MUNINN_BSKY_HANDLE", raising=False)
    monkeypatch.delenv("MUNINN_BSKY_APP_PASSWORD", raising=False)
    monkeypatch.setenv("BSKY_HANDLE", "oskar.example")
    monkeypatch.setenv("BSKY_APP_PASSWORD", "o-pw")
    with pytest.raises(bl.ListError, match="MUNINN_BSKY_HANDLE"):
        bl.auth_for()


# ── source parsing ─────────────────────────────────────────────────────

@pytest.mark.parametrize("source,kind", [
    ("list:at://did:plc:a/app.bsky.graph.list/x", "list"),
    ("starterpack:https://bsky.app/starter-pack/a.example/x", "starterpack"),
    ("followers:alice.example", "followers"),
    ("follows:alice.example", "follows"),
    ("actors:a.example,b.example", "actors"),
    ("https://bsky.app/profile/a.example/lists/x", "list"),
    ("https://bsky.app/starter-pack/a.example/x", "starterpack"),
    ("at://did:plc:a/app.bsky.graph.starterpack/x", "starterpack"),
    ("at://did:plc:a/app.bsky.graph.list/x", "list"),
    ("list:at://did:plc:a/app.bsky.graph.listitem/x", "list"),
])
def test_parse_source_kinds(source, kind):
    """invariant: every prefix and bare-URL form maps to its own kind.

    A list and a starter pack differ by one path segment, and getting it
    backwards builds the wrong list from the wrong members without erroring.

    refuted: swapping the kinds the two bare-URL branches return -> the four
    bare-URL parametrisations went red, each resolving to the other kind.
    Note what did NOT refute it: reordering those two branches changes
    nothing, because their discriminators are disjoint.
    """
    assert bl.parse_source(source)[0] == kind


def test_parse_source_accepts_a_plain_sequence():
    kind, ref = bl.parse_source(["a.example", "did:plc:b"])
    assert (kind, ref) == ("actors", ["a.example", "did:plc:b"])


def test_parse_source_refuses_to_guess():
    """invariant: an unrecognised string errors instead of picking a kind.

    refuted: defaulting the fall-through to "list" -> this test alone went
    red; https://example.com/whatever silently became a list reference.
    """
    with pytest.raises(bl.ListError, match="cannot tell"):
        bl.parse_source("https://example.com/whatever")


# ── source resolution ──────────────────────────────────────────────────

def test_starterpack_resolves_through_its_backing_list(net):
    """invariant: membership comes from the referencelist, not listItemsSample.

    The sample is capped at 12 accounts; the live August 4 Elections pack has
    77. Reading the sample would silently truncate the import.

    refuted: reading pack["listItemsSample"] instead of the backing list ->
    this test alone went red with 1 actor instead of 2.
    """
    table, _ = net
    table["app.bsky.graph.getStarterPack"] = {"starterPack": {
        "record": {"list": "at://did:plc:a/app.bsky.graph.list/BACKING"},
        "listItemsSample": [{"did": "did:plc:sample"}]}}
    table["app.bsky.graph.getList"] = {"items": [
        {"uri": "at://did:plc:a/app.bsky.graph.listitem/1",
         "subject": {"did": "did:plc:1", "handle": "one.example"}},
        {"uri": "at://did:plc:a/app.bsky.graph.listitem/2",
         "subject": {"did": "did:plc:2", "handle": "two.example"}}], "cursor": None}
    out = bl.resolve_source("starterpack:at://did:plc:a/app.bsky.graph.starterpack/x")
    assert out["kind"] == "starterpack"
    assert [a["did"] for a in out["actors"]] == ["did:plc:1", "did:plc:2"]


def test_actors_source_passes_dids_through_without_resolving(net):
    table, sent = net
    out = bl.resolve_source("actors:did:plc:a,did:plc:b")
    assert [a["did"] for a in out["actors"]] == ["did:plc:a", "did:plc:b"]
    assert not sent


# ── writes ─────────────────────────────────────────────────────────────

def test_create_list_rejects_an_unknown_purpose(net):
    """invariant: purpose is checked against PURPOSES before any request.

    refuted: dropping the membership check -> this test alone went red, the
    call reaching createRecord with purpose "reference-list".
    """
    with pytest.raises(bl.ListError, match="purpose must be one of"):
        bl.create_list("x", purpose="reference-list", auth=AUTH)


def test_every_purpose_maps_to_a_defs_uri():
    """invariant: each member of PURPOSES maps to an app.bsky.graph.defs# URI.

    refuted: pointing modlist at a bare "modlist" -> this test alone went red
    naming modlist.
    """
    assert len(PURPOSES) >= 3
    for name, uri in PURPOSES.items():
        assert uri == f"app.bsky.graph.defs#{name}", name


def test_dedupe_and_removal_read_the_repo_not_the_appview(net):
    """invariant: every write path reads own_members, never list_members.

    The AppView lags writes: measured live, it still returned all 77 members
    seconds after two were removed, and deleting from that answer made the
    PDS 500 on records that no longer existed.

    refuted: pointing add_members' skip_existing at list_members -> this test
    alone went red on the unstubbed app.bsky.graph.getList request.
    """
    table, sent = net
    table["com.atproto.repo.listRecords"] = {"records": [
        {"uri": "at://did:plc:me/app.bsky.graph.listitem/i1",
         "value": {"subject": "did:plc:1", "list": LIST}},
        {"uri": "at://did:plc:me/app.bsky.graph.listitem/i2",
         "value": {"subject": "did:plc:other", "list": "at://other/list"}}],
        "cursor": None}
    table["com.atproto.repo.applyWrites"] = {}

    out = bl.add_members(LIST, ["did:plc:1", "did:plc:2"], auth=AUTH)
    assert out == {"added": 1, "skipped": 1, "total": 2}
    assert not any("getList" in s["url"] for s in sent)


def test_own_members_ignores_listitems_belonging_to_other_lists(net):
    table, _ = net
    table["com.atproto.repo.listRecords"] = {"records": [
        {"uri": "at://x/app.bsky.graph.listitem/i1",
         "value": {"subject": "did:plc:1", "list": LIST}},
        {"uri": "at://x/app.bsky.graph.listitem/i2",
         "value": {"subject": "did:plc:2", "list": "at://did:plc:me/app.bsky.graph.list/OTHER"}}],
        "cursor": None}
    assert [m["did"] for m in bl.own_members(LIST, AUTH)] == ["did:plc:1"]


def test_add_members_chunks_at_batch(net):
    """invariant: no applyWrites call carries more than BATCH operations.

    refuted: sending every write in one call -> this test alone went red with
    a single 250-operation batch.
    """
    table, sent = net
    table["com.atproto.repo.applyWrites"] = {}
    bl.add_members(LIST, [f"did:plc:{i}" for i in range(250)], auth=AUTH,
                   skip_existing=False)
    batches = [len(s["body"]["writes"]) for s in sent
               if s["label"].endswith("applyWrites")]
    assert batches == [100, 100, 50]
    assert all(b <= bl.BATCH for b in batches)


def test_add_members_deduplicates_its_own_input(net):
    table, sent = net
    table["com.atproto.repo.applyWrites"] = {}
    out = bl.add_members(LIST, ["did:plc:1", "did:plc:1", "did:plc:2"], auth=AUTH,
                         skip_existing=False)
    assert out == {"added": 2, "skipped": 0, "total": 2}


def test_delete_list_clears_its_listitems_first(net):
    """invariant: deleting a list removes its listitems unless told not to.

    A list record deleted on its own leaves every listitem in the repo
    pointing at a URI that no longer resolves — invisible in every client
    and permanent.

    refuted: making with_members default to False -> this test alone went
    red, no applyWrites reaching the PDS.
    """
    table, sent = net
    table["com.atproto.repo.listRecords"] = {"records": [
        {"uri": "at://did:plc:me/app.bsky.graph.listitem/i1",
         "value": {"subject": "did:plc:1", "list": LIST}}], "cursor": None}
    table["com.atproto.repo.applyWrites"] = {}
    table["com.atproto.repo.deleteRecord"] = {}
    out = bl.delete_list(LIST, auth=AUTH)
    assert out["members_removed"] == 1
    labels = [s["label"] for s in sent]
    assert labels.index("com.atproto.repo.applyWrites") < \
           labels.index("com.atproto.repo.deleteRecord")


def test_build_list_skips_the_dedupe_read_for_a_fresh_list(net):
    """invariant: a list created in this call is not read back before filling.

    refuted: hardcoding skip_existing=True -> this test alone went red on the
    unstubbed listRecords request.
    """
    table, sent = net
    table["com.atproto.repo.createRecord"] = {"uri": LIST, "cid": "c1"}
    table["com.atproto.repo.applyWrites"] = {}
    out = bl.build_list("New", "actors:did:plc:1", auth=AUTH)
    assert out["added"] == 1
    assert not any("listRecords" in s["url"] for s in sent)


# ── transport ──────────────────────────────────────────────────────────

def test_a_transport_failure_is_retried_and_a_4xx_is_not(monkeypatch):
    """invariant: TRIES applies to resets and 5xx; a 400 fails on the first try.

    A single connection reset aborted a 77-member import on the first live
    run, which is what put the retry here.

    refuted: raising on the first exception instead of looping -> this test
    alone went red with attempts == 1.
    """
    import time
    import urllib.error
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    attempts = []

    def flaky(req, timeout=None):
        attempts.append(1)
        raise urllib.error.URLError("reset")

    monkeypatch.setattr(bl.urllib.request, "urlopen", flaky)
    with pytest.raises(bl.ListError, match="unreachable"):
        bl._get("https://x.example/y")
    assert len(attempts) == bl.TRIES

    attempts.clear()

    def four_hundred(req, timeout=None):
        attempts.append(1)
        raise urllib.error.HTTPError("u", 400, "Bad", {}, None)

    monkeypatch.setattr(bl.urllib.request, "urlopen", four_hundred)
    with pytest.raises(bl.ListError, match="HTTP 400"):
        bl._get("https://x.example/y")
    assert len(attempts) == 1


# ── cli ────────────────────────────────────────────────────────────────

def test_every_action_is_callable_and_validates_its_input():
    """invariant: each member of ACTIONS is a callable that rejects {}.

    Every action needs either a list URI, a source, or an explicit identity
    choice; none of them should do something plausible with no arguments.
    whoami is the exception — reporting the identity IS its whole job.

    refuted: adding a no-op action returning {} -> this test went red naming
    it.
    """
    assert len(ACTIONS) >= 6
    for name, fn in ACTIONS.items():
        assert callable(fn), name
        if name == "whoami":
            continue
        with pytest.raises((bl.ListError, KeyError, TypeError)):
            fn({})


# totality: ratchet — atproto defines exactly these three list purposes, and a
# curatelist that quietly stops being offered is a capability lost with a green
# enumeration. The live loop above covers growth; this pins against a loss.
@pytest.mark.parametrize("purpose", ["curatelist", "modlist", "referencelist"])
def test_each_defined_purpose_stays_offered(purpose):
    """invariant: no list purpose is dropped from PURPOSES.

    refuted: removing "modlist" from PURPOSES -> this test went red on the
    modlist parametrisation, alongside test_every_purpose_maps_to_a_defs_uri
    failing its floor. Two reds, which is the point: the floor catches the
    count, this names which member left.
    """
    assert PURPOSES[purpose] == f"app.bsky.graph.defs#{purpose}"


# totality: ratchet — every verb the CLI has shipped. Dropping one removes a
# capability callers may already depend on, and an enumeration over whatever
# ACTIONS now holds cannot see that.
@pytest.mark.parametrize("action", [
    "whoami", "resolve-source", "build-list", "list-members",
    "remove-members", "delete-list"])
def test_each_shipped_action_stays_available(action):
    """invariant: no CLI verb is dropped from ACTIONS.

    refuted: removing "resolve-source" from ACTIONS -> this test went red on
    the resolve-source parametrisation, alongside
    test_every_action_is_callable_and_validates_its_input failing its floor.
    """
    assert action in ACTIONS


def test_main_emits_one_json_object_on_an_unknown_action(capsys):
    assert bl._main(["nope"]) == 2
    assert "unknown action" in json.loads(capsys.readouterr().out)["error"]["message"]


def test_main_wraps_a_list_error_in_the_envelope(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", type("S", (), {"read": lambda self: "{}"})())
    assert bl._main(["delete-list"]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "error"
