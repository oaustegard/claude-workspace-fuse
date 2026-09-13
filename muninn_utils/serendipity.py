"""serendipity — structured serendipity over the memory corpus.

The ``serendipity-usage`` ops entry has documented this API since the boot
restructure. The module never existed: ``import muninn_utils.serendipity`` raised
``ModuleNotFoundError``, the name survived only in ``remembering/scripts/boot.py``,
``defaults/ops.json``, ``_ARCH.md`` and the ops entry itself, and
``recall(tags=['serendipity'])`` returned zero rows across 3303 memories. The
documentation outlived the code because nothing ever called it. This is the
implementation (2026-09-12).

WHY IT EXISTS. Muninn's profile puts her own intellectual interests under
OWN-FACING: "let genuine curiosity emerge from encounters, not from staring
inward... earned through contact with the world, not declared from inside the
egg." Serendipity is the named mechanism for that. Measured 2026-09-12, the
memory store is ~91% negative — 430 correction-tagged entries against 41
satisfaction-analogs — and every registered analog is a work shape. A store that
only records what went wrong has no surface for an encounter to happen on. This
tool manufactures encounters: it puts two unconnected memories side by side and
asks whether there is anything there.

It finds CANDIDATES, not connections. Judging a pair is Muninn's job; roughly
three in four will be nothing, and discarding them quickly is the intended
behaviour, not a failure of the tool.

THREE STRATEGIES, each a different reason two memories might belong together:

- ``rhyme``    high textual similarity, low tag overlap — the same structure
               recurring in an unrelated domain. Delegates to
               ``memory_tfidf.MemoryIndex.cross_domain_rhymes``; the ops entry
               specified BM25, and ``bm25`` is accepted as an alias, but the
               TF-IDF index already in the package does this job and reusing it
               beats a second retrieval stack.
- ``tags``     two or more UNCOMMON tags in common. Shared ``correction`` means
               nothing; shared ``haar-rotation`` means something. Rarity is
               measured against the corpus, not guessed.
- ``temporal`` stored close together in time with little tag overlap — things
               that co-occurred in one session and were never linked.

Every strategy excludes pairs already joined by ``refs`` (that connection is
made), near-duplicates above ``dup_ceiling`` (that is ``memory_tfidf.duplicates``'
job, and a duplicate is not a surprise), and anything tagged ``confidential``
per the private-tag-discipline ops entry — serendipity is exactly the kind of
autonomous surfacing that entry forbids over private projects.

READ-ONLY. Never writes, never fires a trigger. Acting on a pair — ``remember``
with refs, ``supersede``, ``forget`` — stays an explicit Muninn decision.

Usage::

    from muninn_utils.serendipity import serendipity, display
    display(n=5)
    pairs = serendipity(n=5, strategies=["rhyme", "tags", "temporal"])

    # testable / offline — inject rows, fix the sample:
    pairs = serendipity(memories=[{...}, ...], seed=7)

CLI::

    python -m muninn_utils.serendipity            # human-readable
    python -m muninn_utils.serendipity --json
    python -m muninn_utils.serendipity -n 3 --strategies tags,temporal
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass

STRATEGIES = ("rhyme", "tags", "temporal")

# The ops entry named the first strategy "bm25". The package already carries a
# TF-IDF index that does the same job, so the name is an alias rather than a
# second retrieval stack. See upstream-prior-art-check.
_ALIASES = {"bm25": "rhyme", "tfidf": "rhyme", "time": "temporal", "tag": "tags"}

PRIVATE_TAG = "confidential"

# A tag on more than this fraction of the corpus is scaffolding, not signal.
# 'correction' and 'muninn' are shared by hundreds of rows and co-occurrence
# through them is noise.
UNCOMMON_TAG_MAX_DF = 0.02

# Above this cosine similarity a pair is a duplicate, which memory_tfidf.duplicates
# already reports. Serendipity wants the band below it.
DUP_CEILING = 0.75


@dataclass
class Pair:
    """One candidate connection between two memories."""

    strategy: str
    score: float
    why: str
    id_a: str
    id_b: str
    preview_a: str
    preview_b: str
    shared_tags: list
    created_a: str = ""
    created_b: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _tag_set(tags) -> set:
    """Normalise the tags column, which is a JSON string on some read paths and
    already a list on others."""
    if not tags:
        return set()
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except (ValueError, TypeError):
            return {t.strip() for t in tags.split(",") if t.strip()}
    if isinstance(tags, (list, tuple, set)):
        return {str(t) for t in tags if t}
    return set()


def _ref_set(refs) -> set:
    """Same normalisation for refs. Legacy rows carry the literal string 'null'
    (see the recall-empty-diagnostic ops entry)."""
    if not refs or refs == "null":
        return set()
    if isinstance(refs, str):
        try:
            refs = json.loads(refs)
        except (ValueError, TypeError):
            return set()
    if isinstance(refs, (list, tuple, set)):
        return {str(r) for r in refs if r}
    return set()


def _day(row: dict) -> str:
    stamp = row.get("created_at") or row.get("valid_from") or ""
    return str(stamp)[:10]


def _linked(a: dict, b: dict) -> bool:
    """True if either memory already cites the other, by full id or 8-char prefix."""
    refs_a, refs_b = _ref_set(a.get("refs")), _ref_set(b.get("refs"))
    id_a, id_b = str(a.get("id", "")), str(b.get("id", ""))
    for ref in refs_a:
        if ref and (id_b == ref or id_b.startswith(ref) or ref.startswith(id_b)):
            return True
    for ref in refs_b:
        if ref and (id_a == ref or id_a.startswith(ref) or ref.startswith(id_a)):
            return True
    return False


def _overlap(tags_a: set, tags_b: set) -> float:
    if not tags_a or not tags_b:
        return 0.0
    return len(tags_a & tags_b) / len(tags_a | tags_b)


def _fetch_memories() -> list[dict]:
    """Fetch non-deleted memories from Turso. Lazy import so the module loads and
    unit-tests run without the remembering scripts on the path."""
    from scripts.memory import _exec

    return _exec(
        "SELECT id, type, tags, refs, summary, created_at, valid_from, priority "
        "FROM memories WHERE deleted_at IS NULL ORDER BY created_at ASC",
        parse_json=False,
    )


def _public(memories: list[dict]) -> list[dict]:
    """Drop confidential rows. private-tag-discipline: never surface these in an
    autonomous routine, and serendipity is one."""
    return [m for m in memories if PRIVATE_TAG not in _tag_set(m.get("tags"))]


def _preview(row: dict, width: int = 140) -> str:
    return str(row.get("summary") or "")[:width]


def _pair(strategy, score, why, a, b, shared) -> Pair:
    return Pair(
        strategy=strategy,
        score=round(float(score), 3),
        why=why,
        id_a=str(a.get("id", "")),
        id_b=str(b.get("id", "")),
        preview_a=_preview(a),
        preview_b=_preview(b),
        shared_tags=sorted(shared),
        created_a=_day(a),
        created_b=_day(b),
    )


def _by_tags(memories: list[dict], n: int, rng: random.Random) -> list[Pair]:
    """Pairs sharing 2+ uncommon tags and not already linked."""
    total = len(memories)
    if total < 2:
        return []
    ceiling = max(2, int(total * UNCOMMON_TAG_MAX_DF))

    buckets: dict[str, list[int]] = {}
    tag_sets = [_tag_set(m.get("tags")) for m in memories]
    for i, tags in enumerate(tag_sets):
        for tag in tags:
            buckets.setdefault(tag, []).append(i)

    shared_count: dict[tuple[int, int], set] = {}
    for tag, members in buckets.items():
        if len(members) < 2 or len(members) > ceiling:
            continue
        for pos, i in enumerate(members):
            for j in members[pos + 1 :]:
                shared_count.setdefault((i, j), set()).add(tag)

    out = []
    for (i, j), tags in shared_count.items():
        if len(tags) < 2 or _linked(memories[i], memories[j]):
            continue
        out.append(
            _pair(
                "tags",
                len(tags),
                f"{len(tags)} uncommon tags in common, never linked",
                memories[i],
                memories[j],
                tags,
            )
        )
    rng.shuffle(out)
    out.sort(key=lambda p: -p.score)
    return out[:n]


def _by_temporal(
    memories: list[dict], n: int, rng: random.Random, max_tag_overlap: float = 0.2
) -> list[Pair]:
    """Pairs stored the same day with little tag overlap and no refs link."""
    days: dict[str, list[int]] = {}
    for i, m in enumerate(memories):
        day = _day(m)
        if day:
            days.setdefault(day, []).append(i)

    out = []
    for day, members in days.items():
        if len(members) < 2 or len(members) > 40:
            continue
        for pos, i in enumerate(members):
            for j in members[pos + 1 :]:
                a, b = memories[i], memories[j]
                if _linked(a, b):
                    continue
                tags_a, tags_b = _tag_set(a.get("tags")), _tag_set(b.get("tags"))
                if not tags_a or not tags_b:
                    continue
                overlap = _overlap(tags_a, tags_b)
                if overlap > max_tag_overlap:
                    continue
                out.append(
                    _pair(
                        "temporal",
                        1.0 - overlap,
                        f"same session ({day}), tag overlap {overlap:.2f}, never linked",
                        a,
                        b,
                        tags_a & tags_b,
                    )
                )
    rng.shuffle(out)
    return out[:n]


def _by_rhyme(
    memories: list[dict],
    n: int,
    rng: random.Random,
    min_sim: float = 0.3,
    dup_ceiling: float = DUP_CEILING,
    seeds: int = 25,
    same_day_ok: bool = False,
):
    """High textual similarity, low tag overlap — a structure recurring in an
    unrelated domain. Delegates to the TF-IDF index already in the package.

    ``same_day_ok`` defaults False. Two memories written in one session about one
    subject routinely carry different tag vocabularies — a fly body and its
    analysis, a root cause and its stash — so ``max_tag_overlap`` does not
    exclude them and they dominate the high-cosine band. Measured on the first
    live run (2026-09-12, memory ``6082a5fd``): all three returned pairs were
    same-day companions. Same-session pairing is ``temporal``'s job by design, so
    rhyme loses nothing by dropping it.
    """
    if len(memories) < 2:
        return []
    try:
        from muninn_utils.memory_tfidf import MemoryIndex
    except ImportError:
        return []

    # MemoryIndex pins max_df=0.50 and min_df=2, which are incompatible on a
    # corpus small enough that half of it is under two documents — the
    # vectorizer raises "max_df corresponds to < documents than min_df" rather
    # than returning an empty vocabulary. A corpus too small to rhyme is not an
    # error here; it just has no candidates.
    try:
        index = MemoryIndex().build(memories)
    except ValueError:
        return []
    if index.matrix is None:
        return []

    by_id = {str(m.get("id", "")): m for m in memories}
    picks = rng.sample(range(len(memories)), min(seeds, len(memories)))

    out, seen = [], set()
    for i in picks:
        source = memories[i]
        source_id = str(source.get("id", ""))
        if not source_id:
            continue
        try:
            rhymes = index.cross_domain_rhymes(source_id, n=3, min_sim=min_sim)
        except KeyError:
            continue
        for r in rhymes:
            target = by_id.get(str(r["id"]))
            if target is None or r["score"] >= dup_ceiling:
                continue
            key = tuple(sorted((source_id, str(r["id"]))))
            if key in seen or _linked(source, target):
                continue
            if not same_day_ok and _day(source) and _day(source) == _day(target):
                continue
            seen.add(key)
            out.append(
                _pair(
                    "rhyme",
                    r["score"],
                    f"cosine {r['score']:.2f}, tag overlap {r['tag_overlap']:.2f} "
                    "— same shape, different domain",
                    source,
                    target,
                    set(r.get("shared_tags") or []),
                )
            )
    out.sort(key=lambda p: -p.score)
    return out[:n]


def serendipity(
    n: int = 5,
    strategies: list | tuple | None = None,
    *,
    memories: list[dict] | None = None,
    seed: int | None = None,
    same_day_ok: bool = False,
) -> list[Pair]:
    """Return up to ``n`` candidate pairs per strategy.

    ``memories`` injects rows for offline or test use; omitted, the corpus is read
    from Turso. ``seed`` fixes the sampling so a run is reproducible — leave it
    None in normal use, since a fresh sample is the point. ``same_day_ok`` is
    passed through to the rhyme strategy, which drops same-session pairs by
    default; see ``_by_rhyme``.
    """
    rows = _public(memories if memories is not None else _fetch_memories())
    rng = random.Random(seed)

    wanted = [str(s).lower() for s in (strategies or STRATEGIES)]
    wanted = [_ALIASES.get(s, s) for s in wanted]
    unknown = [s for s in wanted if s not in STRATEGIES]
    if unknown:
        raise ValueError(f"unknown strategies {unknown}; known: {list(STRATEGIES)}")

    out: list[Pair] = []
    for name in dict.fromkeys(wanted):
        if name == "rhyme":
            out.extend(_by_rhyme(rows, n, rng, same_day_ok=same_day_ok))
        elif name == "tags":
            out.extend(_by_tags(rows, n, rng))
        elif name == "temporal":
            out.extend(_by_temporal(rows, n, rng))
    return out


def format_pairs(pairs: list[Pair]) -> str:
    """Render pairs for reading. The ops entry's four verdicts are the menu:
    real connection → refs; duplicate → supersede+forget; nothing → discard;
    uncertain → flag."""
    if not pairs:
        return "SERENDIPITY — no candidate pairs.\n"

    lines = ["SERENDIPITY — CANDIDATE PAIRS", "=" * 52, ""]
    current = None
    for p in pairs:
        if p.strategy != current:
            current = p.strategy
            lines.append(f"[{current.upper()}]")
        lines.append(f"  {p.id_a[:8]} <-> {p.id_b[:8]}   {p.why}")
        lines.append(f"    A ({p.created_a}) {p.preview_a}")
        lines.append(f"    B ({p.created_b}) {p.preview_b}")
        if p.shared_tags:
            lines.append(f"    shared: {', '.join(p.shared_tags[:6])}")
        lines.append("")
    lines.append("Verdicts: refs / supersede+forget / discard / flag.")
    return "\n".join(lines) + "\n"


def display(n: int = 5, strategies: list | tuple | None = None, **kwargs) -> None:
    """Pretty-print n candidate pairs per strategy."""
    print(format_pairs(serendipity(n=n, strategies=strategies, **kwargs)))


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Structured serendipity over the memory corpus.")
    parser.add_argument("-n", type=int, default=5, help="pairs per strategy (default 5)")
    parser.add_argument(
        "--strategies",
        default=",".join(STRATEGIES),
        help=f"comma-separated subset of {list(STRATEGIES)}",
    )
    parser.add_argument("--seed", type=int, default=None, help="fix sampling for reproducibility")
    parser.add_argument(
        "--same-day-ok",
        action="store_true",
        help="let the rhyme strategy return same-session pairs (off by default)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    pairs = serendipity(
        n=args.n,
        strategies=[s for s in args.strategies.split(",") if s],
        seed=args.seed,
        same_day_ok=args.same_day_ok,
    )
    if args.json:
        print(json.dumps([p.to_dict() for p in pairs], indent=2))
    else:
        print(format_pairs(pairs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
