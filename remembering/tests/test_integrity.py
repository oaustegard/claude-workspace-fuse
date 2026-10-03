"""Tests for scripts/integrity.py — supersession lineage and flag repair.

Pure functions take row dicts; the store-touching ones are exercised with a
mocked `_exec` / `_exec_batch`. The fixtures model the shapes the live store
actually holds (measured 2026-09-17): signature supersessions, rows flagged
by the old refs-as-supersede conflation, and 8-character prefix refs.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import integrity as ig  # noqa: E402

T1 = "2026-08-01T10:00:00.000001Z"
T2 = "2026-08-02T10:00:00.000002Z"


def uid(ch):
    c = ch * 8
    return f"{c}-{ch * 4}-{ch * 4}-{ch * 4}-{ch * 12}"


A, B, C, D, E, F = (uid(x) for x in "abcdef")


def row(mid, refs="[]", created=T1, deleted=None, flag=0, by=None):
    return dict(id=mid, refs=refs, created_at=created, deleted_at=deleted,
                is_superseded=flag, superseded_by=by)


def sole(target):
    return f'["{target}"]'


# ── load_refs / ref_id ──

def test_load_refs_shapes():
    assert ig.load_refs('["x"]') == ["x"]
    assert ig.load_refs("['x']") == ["x"]
    assert ig.load_refs("null") == []
    assert ig.load_refs(None) == []
    assert ig.load_refs("") == []
    assert ig.load_refs("not json") is None
    assert ig.load_refs(["y"]) == ["y"]


def test_ref_id_skips_typed_objects_and_non_ids():
    assert ig.ref_id(A) == A
    assert ig.ref_id({"id": A, "rel": "extends"}) == A
    assert ig.ref_id({"_type": "alternatives", "items": []}) is None
    assert ig.ref_id("https://example.com") is None
    assert ig.ref_id("oaustegard/remex#4") is None
    assert ig.ref_id("abcd1234") == "abcd1234"


# ── supersession_links ──

def test_signature_links_original_to_replacement():
    rows = [row(A, deleted=T2, flag=1), row(B, refs=sole(A), created=T2)]
    assert ig.supersession_links(rows) == {A: B}


def test_citation_with_different_timestamp_is_not_a_supersession():
    rows = [row(A, deleted=T2, flag=1), row(B, refs=sole(A), created=T1)]
    assert ig.supersession_links(rows) == {}


def test_live_original_is_never_linked():
    # supersede() always retires the original; a live cited row was not replaced.
    rows = [row(A, flag=1), row(B, refs=sole(A), created=T2)]
    assert ig.supersession_links(rows) == {}


def test_annotated_or_multi_ref_citer_is_not_the_signature():
    rows = [
        row(A, deleted=T2, flag=1),
        row(B, refs=f'[{{"id": "{A}", "rel": "supersedes"}}]', created=T2),
        row(C, refs=f'["{A}", "{D}"]', created=T2),
        row(D),
    ]
    assert ig.supersession_links(rows) == {}


def test_ambiguous_replacements_are_left_out():
    rows = [row(A, deleted=T2), row(B, refs=sole(A), created=T2), row(C, refs=sole(A), created=T2)]
    assert ig.supersession_links(rows) == {}


def test_partial_id_citer_is_not_the_signature():
    rows = [row(A, deleted=T2), row(B, refs=sole(A[:8]), created=T2)]
    assert ig.supersession_links(rows) == {}


def test_flag_is_not_required_to_link():
    # A legacy DB without is_superseded still yields its supersessions.
    rows = [row(A, deleted=T2, flag=0), row(B, refs=sole(A), created=T2)]
    assert ig.supersession_links(rows) == {A: B}


# ── plan_repairs ──

def test_plan_links_missing_pointer_and_skips_complete_ones():
    rows = [
        row(A, deleted=T2, flag=1), row(B, refs=sole(A), created=T2),
        row(C, deleted=T2, flag=1, by=D), row(D, refs=sole(C), created=T2),
    ]
    plan = ig.plan_repairs(rows)
    assert plan["link"] == [(A, B)]
    assert plan["unflag"] == []


def test_plan_sets_missing_flag_even_when_pointer_present():
    rows = [row(A, deleted=T2, flag=0, by=B), row(B, refs=sole(A), created=T2)]
    assert ig.plan_repairs(rows)["link"] == [(A, B)]


def test_plan_unflags_live_rows_nothing_replaced():
    rows = [
        row(A, flag=1),                      # conflation residue: hidden from recall
        row(B, refs=sole(A), created=T2),    # an ordinary citation of A
        row(C, flag=1, deleted=T1),          # retired: flag is harmless, left alone
        row(E, flag=1, by=F),                # names a replacement: not ours to clear
        row(F),
    ]
    assert ig.plan_repairs(rows)["unflag"] == [A]


# ── resolve_prefixes ──

def test_resolve_unique_prefixes_only():
    known = {A, B, "abcdef12-0000-0000-0000-000000000000", "abcdef12-1111-0000-0000-000000000000"}
    got = ig.resolve_prefixes([A[:8], B[:10], "abcdef12", "0badbeef", A, "short"], known)
    assert got == {A[:8]: A, B[:10]: B}


def test_resolve_prefix_is_case_insensitive():
    assert ig.resolve_prefixes([A[:8].upper()], {A}) == {A[:8].upper(): A}


# ── successor_chain ──

def test_successor_chain_follows_and_stops_on_cycle():
    assert ig.successor_chain(A, {A: B, B: C}) == [A, B, C]
    assert ig.successor_chain(A, {A: B, B: A}) == [A, B]
    assert ig.successor_chain(D, {A: B}) == [D]


# ── store-touching functions, mocked ──

def test_repair_dry_run_writes_nothing():
    rows = [row(A, deleted=T2, flag=1), row(B, refs=sole(A), created=T2), row(C, flag=1)]
    with patch("scripts.turso._exec_batch") as batch:
        plan = ig.repair(write=False, rows=rows)
    assert plan["counts"] == {"link": 1, "unflag": 1}
    assert plan["written"] is False
    batch.assert_not_called()


def test_repair_write_issues_guarded_updates():
    rows = [row(A, deleted=T2, flag=1), row(B, refs=sole(A), created=T2), row(C, flag=1)]
    with patch("scripts.turso._exec_batch") as batch:
        plan = ig.repair(write=True, rows=rows)
    assert plan["written"] is True
    stmts = batch.call_args[0][0]
    assert ("UPDATE memories SET superseded_by = ?, is_superseded = 1 WHERE id = ?", [B, A]) in stmts
    unflag = [s for s in stmts if "is_superseded = 0" in s[0]]
    assert unflag and unflag[0][1] == [C]
    # The unflag must re-check its own precondition in SQL, so a row retired or
    # linked between plan and write is not touched.
    assert "deleted_at IS NULL" in unflag[0][0] and "superseded_by IS NULL" in unflag[0][0]


def test_successor_walks_pointer_chain():
    table = {A: B, B: C, C: None}

    def fake_exec(sql, params=None):
        key = params[0]
        if "LIKE" in sql:
            hits = [k for k in table if k.startswith(key.rstrip("%"))]
            return [{"id": k, "superseded_by": table[k]} for k in hits]
        return [{"id": key, "superseded_by": table[key]}] if key in table else []

    with patch("scripts.turso._exec", side_effect=fake_exec):
        assert ig.successor(A[:8]) == C
        assert ig.successor(C) == C
        assert ig.successor("0badbeef") is None


# ── memory.py integration, mocked ──

def test_supersede_writes_pointer_in_the_retiring_update():
    from scripts import memory as mm
    mm._SUPERSEDED_BY_READY = True
    with patch("scripts.memory._exec", return_value=[{"priority": 0}]), \
         patch("scripts.memory._exec_batch") as batch, \
         patch("scripts.memory.config_get", return_value=None):
        new_id = mm.supersede(A, "replacement", "decision")
    retire = batch.call_args[0][0][0]
    assert "superseded_by = ?" in retire[0]
    assert retire[1] == [retire[1][0], str(new_id), A]


def test_supersede_ensures_column_once_per_process():
    from scripts import memory as mm
    mm._SUPERSEDED_BY_READY = False
    calls = []

    def fake_exec(sql, params=None):
        calls.append(sql)
        return [{"priority": 0}]

    with patch("scripts.memory._exec", side_effect=fake_exec), \
         patch("scripts.memory._exec_batch"), \
         patch("scripts.memory.config_get", return_value=None):
        mm.supersede(A, "one", "decision")
        mm.supersede(A, "two", "decision")
    assert sum("ADD COLUMN superseded_by" in c for c in calls) == 1


def test_write_expands_unique_prefix_refs_and_keeps_other_shapes():
    from scripts import memory as mm

    def fake_exec(sql, params=None):
        if "LIKE" in sql:
            return [{"id": A}] if A.startswith(params[0].rstrip("%")) else []
        return []

    alt = {"_type": "alternatives", "items": []}
    with patch("scripts.memory._exec", side_effect=fake_exec):
        out = mm._expand_refs([A[:8], {"id": A[:8], "rel": "extends"}, B, "0badbeef", None, alt, "repo#4"])
    assert out == [A, {"id": A, "rel": "extends"}, B, "0badbeef", alt, "repo#4"]


def test_forget_leaves_superseded_flags_alone():
    from scripts import memory as mm
    sqls = []

    def fake_exec(sql, params=None):
        sqls.append(sql)
        return [{"tags": "[]", "refs": f'["{B}"]'}]

    with patch("scripts.memory._exec", side_effect=fake_exec):
        mm.forget(A)
    assert not any("is_superseded" in s for s in sqls)


def test_remember_write_path_uses_expansion():
    from scripts import memory as mm
    inserted = []

    def fake_exec(sql, params=None):
        if "LIKE" in sql:
            return [{"id": A}]
        if sql.lstrip().startswith("INSERT"):
            inserted.append(params)
        return []

    with patch("scripts.memory._exec", side_effect=fake_exec):
        mm._write_memory(C, "s", "decision", T1, 0.8, [], [A[:8]], 0, None, None)
    assert inserted and inserted[0][6] == f'["{A}"]'


def test_boot_signal_fires_is_silent_at_zero_and_reports_failure():
    assert "3 live memories hidden" in ig.boot_signal(lambda sql: [{"n": "3"}])
    assert ig.boot_signal(lambda sql: [{"n": "0"}]) == ""

    def boom(sql):
        raise RuntimeError("down")
    assert ig.boot_signal(boom).startswith("lineage check failed")
