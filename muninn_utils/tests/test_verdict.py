"""verdict — the fingerprint must date a verdict, and must fail loud when it can't.

Everything here runs offline: criterion prose is written into a tmp_path root and
memory rows are injected, so no Turso config and no `challenging` install is
needed.

    python3 -m pytest muninn_utils/tests/test_verdict.py
"""
from __future__ import annotations

import json

import pytest

from muninn_utils.verdict import (
    VERDICT_TAG,
    CriterionUnavailable,
    count_verdicts,
    criterion_text,
    fingerprint,
    format_report,
    stale_verdicts,
    store_verdict,
    verdict_tags,
)


@pytest.fixture
def root(tmp_path):
    (tmp_path / "prose.md").write_text("# prose\nfindings must be actionable.\n")
    (tmp_path / "prose-register.md").write_text("# register\nmatch the voice.\n")
    return tmp_path


def row(mem_id: str, tags: list, **extra) -> dict:
    return {"id": mem_id, "summary": f"verdict {mem_id}", "tags": tags, **extra}


# ── the fingerprint ───────────────────────────────────────────────────────────

def test_fingerprint_changes_when_the_criterion_prose_changes(root):
    """invariant: editing the rubric changes the hash. This is the whole point.

    refuted, measured 2026-09-10: replacing the hash input with the profile
    NAME fails 7 of the 16 tests here — this one, both voice tests, the
    unreadable-criterion guard, and the three staleness tests. Nine still pass,
    so a fingerprint that never moves would still look like a working module
    from the storage side alone.
    """
    before = fingerprint("prose", judge="gemini", root=root)["crit_sha"]
    (root / "prose.md").write_text("# prose\nfindings must be actionable AND ranked.\n")
    after = fingerprint("prose", judge="gemini", root=root)["crit_sha"]
    assert before != after


def test_fingerprint_covers_the_voice_signature(root):
    """invariant: for a voice profile, the signature is part of the criterion.

    The prose-register signature is edited far more often than the profile file.
    A hash blind to it would report every register verdict current forever.
    """
    a = fingerprint("prose-register", voice="lead with the finding", root=root)["crit_sha"]
    b = fingerprint("prose-register", voice="lead with the finding. no bird puns.",
                    root=root)["crit_sha"]
    assert a != b


def test_voice_profile_without_a_voice_is_refused(root):
    """invariant: a register fingerprint that silently omitted the signature
    would assert a provenance that did not happen."""
    with pytest.raises(ValueError, match="voice signature"):
        fingerprint("prose-register", root=root)


def test_voice_on_a_non_voice_profile_is_refused(root):
    with pytest.raises(ValueError, match="takes no voice"):
        fingerprint("prose", voice="something", root=root)


def test_unreadable_criterion_raises_rather_than_degrading(root):
    """invariant: a missing rubric is an error, not a placeholder hash.

    Degrading to a constant would compare unequal to every stored hash and
    report the entire corpus stale — a confident wrong answer, which is worse
    than no answer. Same rule as CLAUDE.md's 'degrade to None, never to ""'.
    """
    with pytest.raises(CriterionUnavailable):
        fingerprint("nonexistent-profile", root=root)


def test_criterion_text_is_the_file_contents(root):
    assert "findings must be actionable" in criterion_text("prose", root=root)


# ── storage ───────────────────────────────────────────────────────────────────

def test_store_verdict_writes_the_fingerprint_into_tags(root):
    """invariant: what gets stored is queryable by the staleness pass."""
    captured = {}

    def fake_remember(summary, mem_type, **kw):
        captured.update(summary=summary, type=mem_type, **kw)
        return "mem-1234"

    fp = fingerprint("prose", judge="gemini", root=root)
    mid = store_verdict(
        {"verdict": "REVISE", "summary": "two staged closers",
         "findings": [{"issue": "aphoristic closer in para 3"}]},
        subject="blog/draft.html", refs=["src-1"], _remember=fake_remember, **fp,
    )

    assert mid == "mem-1234"
    assert f"crit-sha:{fp['crit_sha']}" in captured["tags"]
    assert "judge:gemini" in captured["tags"]
    assert "criterion:prose" in captured["tags"]
    assert VERDICT_TAG in captured["tags"]
    assert captured["refs"] == ["src-1"]
    assert "REVISE" in captured["summary"]
    assert "aphoristic closer" in captured["summary"]


def test_stored_tags_match_what_the_query_parses(root):
    """invariant: writer and reader use one tag vocabulary.

    refuted: changing the prefix in verdict_tags() to `sha:` without changing
    the query makes every stored verdict read as pre-fingerprint and therefore
    permanently stale — the failure would look like data, not like a bug.
    """
    fp = fingerprint("prose", judge="claude", root=root)
    tags = verdict_tags(fp["judge"], fp["profile"], fp["crit_sha"])
    fresh = stale_verdicts("prose", memories=[row("m1", tags)], root=root)
    assert fresh == []


# ── staleness ─────────────────────────────────────────────────────────────────

def test_verdict_goes_stale_when_the_criterion_moves(root):
    fp = fingerprint("prose", judge="gemini", root=root)
    rows = [row("m1", verdict_tags("gemini", "prose", fp["crit_sha"]))]
    assert stale_verdicts("prose", memories=rows, root=root) == []

    (root / "prose.md").write_text("# prose\nrewritten rubric.\n")
    stale = stale_verdicts("prose", memories=rows, root=root)
    assert len(stale) == 1
    assert stale[0]["id"] == "m1"
    assert stale[0]["crit_sha"] == fp["crit_sha"]
    assert stale[0]["current_sha"] != fp["crit_sha"]


def test_verdicts_without_a_fingerprint_are_stale_not_current(root):
    """invariant: unknown provenance is not the same as current.

    Verdicts stored before this module carry no crit-sha. Treating those as
    matching is exactly how a rewritten rubric goes unnoticed, so they surface
    with crit_sha=None.
    """
    rows = [row("old", [VERDICT_TAG, "criterion:prose"])]
    stale = stale_verdicts("prose", memories=rows, root=root)
    assert len(stale) == 1 and stale[0]["crit_sha"] is None


def test_other_profiles_are_not_swept_in(root):
    fp = fingerprint("prose", judge="gemini", root=root)
    reg = fingerprint("prose-register", voice="v", judge="gemini", root=root)
    rows = [
        row("m1", verdict_tags("gemini", "prose", "deadbeefdead")),
        row("m2", verdict_tags("gemini", "prose-register", reg["crit_sha"])),
    ]
    stale = stale_verdicts("prose", memories=rows, root=root)
    assert [s["id"] for s in stale] == ["m1"]
    assert fp["crit_sha"] != "deadbeefdead"


def test_non_verdict_memories_are_ignored(root):
    rows = [row("m1", ["analysis", "paper-insight"]),
            row("m2", verdict_tags("gemini", "prose", "aaaaaaaaaaaa"))]
    assert [s["id"] for s in stale_verdicts("prose", memories=rows, root=root)] == ["m2"]


def test_tags_stored_as_a_json_string_are_parsed(root):
    """invariant: rows come back from Turso with tags as a JSON blob, not a list."""
    tags = verdict_tags("gemini", "prose", "aaaaaaaaaaaa")
    rows = [row("m1", json.dumps(tags))]
    assert [s["id"] for s in stale_verdicts("prose", memories=rows, root=root)] == ["m1"]


def test_all_profiles_when_none_named(root):
    rows = [
        row("m1", verdict_tags("gemini", "prose", "aaaaaaaaaaaa")),
        row("m2", verdict_tags("gemini", "prose-register", "bbbbbbbbbbbb")),
    ]
    stale = stale_verdicts(voice="v", memories=rows, root=root)
    assert {s["id"] for s in stale} == {"m1", "m2"}


# ── the promotion trigger ─────────────────────────────────────────────────────

def test_count_verdicts_counts_only_verdicts(root):
    rows = [row("m1", verdict_tags("gemini", "prose", "a" * 12)),
            row("m2", ["analysis"]),
            row("m3", verdict_tags("claude", "code", "b" * 12))]
    assert count_verdicts(memories=rows) == 2


def test_format_report_is_readable_when_empty():
    assert "matches its criterion" in format_report([], "prose")
