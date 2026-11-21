"""verdict — persist a `challenge()` verdict with the fingerprint that dates it.

WHY THIS EXISTS
---------------
`challenge()` (the `challenging` skill) is Muninn's semantic operator: a model
reads an artifact against a named criterion and returns
``{verdict, findings, strengths, summary}``. It writes nothing. Every verdict it
has ever produced died with its session, so "has this draft already been through
prose-register?" and "which of my stored conclusions rest on a criterion I have
since rewritten?" are both unanswerable.

Storing the verdict alone would not fix the second question. A verdict is only
meaningful relative to three things that all change underneath it:

* the **judge** — gemini, claude, or self, resolved from whatever credentials
  happened to be present at call time;
* the **criterion** — a profile's system prompt, which is prose in
  ``challenging/references/<profile>.md`` and gets edited;
* the **voice signature**, for ``prose-register``, which is a separate body of
  prose that gets edited more often than the profile does.

A judgement made under criterion-v1 is not a judgement under criterion-v2, and
nothing about the stored text says which one it was. So this module stores the
verdict together with a content hash of the criterion that produced it, which
makes staleness a query instead of a guess:

    stale_verdicts('prose-register')   # verdicts predating the current signature

That is TrajectoryDB's §3.3.2/§4.3.3 point (arXiv:2609.07782) applied to the one
semantic operator Muninn actually runs: existing semantic caches key reuse on
input similarity, which cannot see that the *rubric* moved.

WHAT THIS DELIBERATELY IS NOT
-----------------------------
There is no schema column and no migration. Measured 2026-09-10 against the live
store: 3,275 live memories, of which the ones that are a model's verdict under a
named criterion number in the low tens (``challenge`` 3, ``judge`` 8, ``verdict``
3, ``adversarial`` 13, ``prose-register`` 8). A column, an index and an API
parameter for tens of rows is the failure in memory ``ecfe464f``. The fingerprint
rides in tags, which the existing corpus can hold comfortably at this size.

PROMOTION TRIGGER, so this decision is re-checkable rather than permanent: when
``count_verdicts()`` passes ~2,000, tag-scanning becomes the query shape that
broke boot in 2026-08 (a leading-wildcard LIKE over the tags blob, 5,063 rows,
~46 s). At that point either add the partial index the ``remind-*`` states use,
or promote ``crit-sha`` to a real column. Not before.

Usage::

    from muninn_utils.verdict import fingerprint, store_verdict, stale_verdicts

    fp = fingerprint('prose-register', voice=signature_text, judge='gemini')
    result = challenge(draft, profile='prose-register', voice=signature_text)
    store_verdict(result, subject='blog/no-server-at-all.html', **fp)

    for m in stale_verdicts('prose-register'):
        print(m['id'], m['summary'][:80])

CLI::

    python -m muninn_utils.verdict --stale prose-register
    python -m muninn_utils.verdict --count
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

#: Where the `challenging` skill keeps one prose file per review profile. Each
#: file's text IS the criterion; hashing it is what dates a verdict.
CRITERION_ROOT = Path(
    os.environ.get("CHALLENGING_REFERENCES", "/mnt/skills/user/challenging/references")
)

#: Tag every stored verdict carries, and the query handle for all of them.
VERDICT_TAG = "verdict"

#: Profiles that take a separate voice signature. For these the criterion is the
#: profile prose AND the signature, because either one moving invalidates the
#: judgement and only the pair identifies it.
VOICE_PROFILES = ("prose-register",)

#: Hash prefix length. 12 hex = 48 bits; collision risk is nil at this corpus
#: size and the tag stays readable in a recall dump.
SHA_LEN = 12


class CriterionUnavailable(RuntimeError):
    """The profile's criterion prose could not be read.

    Raised rather than degraded to a placeholder hash: a fingerprint computed
    over text we could not read would compare unequal to every real one and
    report the whole corpus stale, which is worse than not answering.
    """


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:SHA_LEN]


def criterion_text(profile: str, voice: str = "", *, root: Path | None = None) -> str:
    """Return the exact prose a verdict under `profile` was judged against.

    `voice` is appended for the profiles that take one, so the pair is hashed as
    a single criterion. Passing a voice to a profile that does not take one is a
    caller error and raises — silently ignoring it would produce a fingerprint
    that claims to cover a signature it never read.
    """
    root = root or CRITERION_ROOT
    path = root / f"{profile}.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise CriterionUnavailable(f"cannot read criterion for {profile!r} at {path}: {e}") from e

    if voice and profile not in VOICE_PROFILES:
        raise ValueError(
            f"profile {profile!r} takes no voice signature; got {len(voice)} chars. "
            f"Voice profiles: {', '.join(VOICE_PROFILES)}"
        )
    if profile in VOICE_PROFILES and not voice:
        raise ValueError(
            f"profile {profile!r} is judged against a voice signature; pass voice=... "
            f"or the fingerprint will not identify the criterion that was used"
        )
    return text + ("\n\n---VOICE---\n" + voice if voice else "")


def fingerprint(profile: str, voice: str = "", judge: str = "unknown",
                *, root: Path | None = None) -> dict:
    """Compute the {judge, profile, crit_sha} triple that dates a verdict.

    Call this with the SAME voice text handed to `challenge()`. A fingerprint
    computed from a different signature than the one the judge saw is worse than
    none — it asserts a provenance that did not happen.
    """
    return {
        "judge": judge,
        "profile": profile,
        "crit_sha": _sha(criterion_text(profile, voice, root=root)),
    }


def verdict_tags(judge: str, profile: str, crit_sha: str, extra: list | None = None) -> list:
    """Canonical tag list. Kept in one place so the writer and the staleness
    query cannot drift apart — they parse the same strings."""
    return [
        VERDICT_TAG,
        f"judge:{judge}",
        f"criterion:{profile}",
        f"crit-sha:{crit_sha}",
        *(extra or []),
    ]


def _summarise(result: dict, subject: str, judge: str, profile: str) -> str:
    findings = result.get("findings") or []
    lines = [
        f"VERDICT [{profile}] on {subject}: {result.get('verdict', '?')} "
        f"({len(findings)} finding(s), judge={judge})",
    ]
    if result.get("summary"):
        lines.append(str(result["summary"]).strip())
    for f in findings:
        if isinstance(f, dict):
            lines.append(f"  - {f.get('issue') or f.get('title') or json.dumps(f)[:160]}")
        else:
            lines.append(f"  - {str(f)[:160]}")
    return "\n".join(lines)


def store_verdict(result: dict, *, subject: str, judge: str, profile: str,
                  crit_sha: str, refs: list | None = None, tags: list | None = None,
                  priority: int = 0, _remember=None) -> str:
    """Persist one `challenge()` result with its fingerprint. Returns memory id.

    `subject` names what was judged — a path, a URL, a memory id, a PR. `refs`
    carries the evidence edges as usual; the fingerprint is about the judging,
    not the evidence.
    """
    if _remember is None:  # injected in tests; import is deferred so the module
        from remembering import remember  # imports without a live Turso config
        _remember = remember

    mid = _remember(
        _summarise(result, subject, judge, profile),
        "analysis",
        tags=verdict_tags(judge, profile, crit_sha, tags),
        refs=refs or [],
        priority=priority,
    )
    return str(mid)


def _tag_value(tags, prefix: str) -> str | None:
    for t in tags or []:
        if isinstance(t, str) and t.startswith(prefix):
            return t[len(prefix):]
    return None


def _as_tags(row) -> list:
    tags = row.get("tags") if isinstance(row, dict) else getattr(row, "tags", None)
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except (ValueError, TypeError):
            tags = []
    return tags or []


def stale_verdicts(profile: str | None = None, voice: str = "", *,
                   memories: list | None = None, root: Path | None = None,
                   n: int = 200, _recall=None) -> list:
    """Stored verdicts whose criterion has changed since they were made.

    A verdict is stale when its `crit-sha` differs from the hash of the criterion
    text as it reads now. Verdicts carrying no `crit-sha` predate this module and
    come back as stale with `crit_sha=None` — unknown provenance is not the same
    as current, and treating it as current is how a rewritten rubric goes
    unnoticed.

    Pass `memories=` to run offline against injected rows.
    """
    if memories is None:
        if _recall is None:
            from remembering import recall
            _recall = recall
        memories = _recall(query="verdict", tags=[VERDICT_TAG], n=n) or []

    current: dict[str, str] = {}
    stale = []
    for row in memories:
        tags = _as_tags(row)
        if VERDICT_TAG not in tags:
            continue
        row_profile = _tag_value(tags, "criterion:")
        if profile is not None and row_profile != profile:
            continue
        if row_profile is None:
            continue
        if row_profile not in current:
            # `voice` applies only to the profiles judged against one. Sweeping
            # every profile at once must not hand a signature to a profile that
            # rejects it.
            v = voice if row_profile in VOICE_PROFILES else ""
            current[row_profile] = _sha(criterion_text(row_profile, v, root=root))
        row_sha = _tag_value(tags, "crit-sha:")
        if row_sha != current[row_profile]:
            entry = row if isinstance(row, dict) else {"id": getattr(row, "id", None)}
            stale.append({**entry, "crit_sha": row_sha, "current_sha": current[row_profile]})
    return stale


def count_verdicts(*, memories: list | None = None, n: int = 5000, _recall=None) -> int:
    """How many stored verdicts exist. Read against the promotion trigger in the
    module docstring before deciding this should become a schema column."""
    if memories is None:
        if _recall is None:
            from remembering import recall
            _recall = recall
        memories = _recall(query="verdict", tags=[VERDICT_TAG], n=n) or []
    return sum(1 for row in memories if VERDICT_TAG in _as_tags(row))


def format_report(stale: list, profile: str | None = None) -> str:
    head = f"stale verdicts{f' [{profile}]' if profile else ''}: {len(stale)}"
    if not stale:
        return head + " — every stored verdict matches its criterion as it reads now"
    lines = [head]
    for s in stale:
        was = s.get("crit_sha") or "none (pre-fingerprint)"
        lines.append(f"  {s.get('id', '?')}  was {was} → now {s.get('current_sha')}")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--stale", metavar="PROFILE", help="list verdicts whose criterion moved")
    ap.add_argument("--voice", default="", help="voice signature, for voice profiles")
    ap.add_argument("--count", action="store_true", help="how many verdicts are stored")
    args = ap.parse_args()

    if args.count:
        print(count_verdicts())
    elif args.stale:
        print(format_report(stale_verdicts(args.stale, args.voice), args.stale))
    else:
        ap.print_help()
