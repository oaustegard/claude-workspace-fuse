"""Cluster memories into KB files by their primary tag.

For each memory, pick the most-informative tag: skip date/numeric/meta tags,
prefer tags that match other memories in the corpus (so we don't end up with
many singleton files), and use the corpus-wide tag frequency as a tiebreaker.
"""

from __future__ import annotations
from collections import Counter, defaultdict

from .config import TAG_META, TAG_META_PATTERNS, TAG_ALIASES


# ─── Tag classification ─────────────────────────────────────────────────────

def is_meta_tag(tag: str) -> bool:
    """True if `tag` shouldn't be used as a primary cluster tag."""
    if tag in TAG_META:
        return True
    for pat in TAG_META_PATTERNS:
        if pat.match(tag):
            return True
    return False


def _canonicalize(tag: str) -> str:
    """Map a tag to its canonical form via TAG_ALIASES (identity if absent)."""
    return TAG_ALIASES.get(tag, tag)


def candidate_tags(tags: list[str]) -> list[str]:
    """Canonical, deduplicated, non-meta candidate tags."""
    seen = set()
    out = []
    for t in tags:
        c = _canonicalize(t)
        if c in seen or is_meta_tag(c):
            continue
        seen.add(c)
        out.append(c)
    return out


# ─── Primary tag selection ──────────────────────────────────────────────────

def build_tag_frequencies(memories: list[dict]) -> Counter:
    """Corpus-wide count of candidate tags."""
    c: Counter = Counter()
    for m in memories:
        for t in candidate_tags(m.get("tags", [])):
            c[t] += 1
    return c


def pick_primary_tag(memory: dict, freq: Counter) -> str:
    """Choose the primary tag for one memory.

    Rule: among candidate tags (non-meta), pick the highest-frequency one in
    the corpus. Ties broken by alphabetical order (stable). If no candidate,
    fall back to '_misc'.
    """
    cand = candidate_tags(memory.get("tags", []))
    if not cand:
        return "_misc"
    cand.sort()  # alpha for tiebreak
    cand.sort(key=lambda t: freq.get(t, 0), reverse=True)
    return cand[0]


# ─── Clustering ─────────────────────────────────────────────────────────────

def cluster_by_primary_tag(
    memories: list[dict],
    *,
    max_cluster_size: int = 30,
    min_cluster_size: int = 2,
) -> dict[str, list[dict]]:
    """Group memories by primary tag.

    Two-pass:
    1. First pass picks the highest-frequency candidate tag per memory.
    2. If a memory's primary tag has < min_cluster_size members, re-route
       it to the highest-frequency *non-singleton* candidate. Fall back to
       `_misc` if no candidate has a real cluster home.

    Clusters larger than `max_cluster_size` are split chronologically into
    {tag}-1, {tag}-2, ... suffixed buckets.
    """
    freq = build_tag_frequencies(memories)

    # Pass 1: provisional assignment
    for m in memories:
        m["primary_tag"] = pick_primary_tag(m, freq)

    # Count provisional cluster sizes
    provisional: Counter = Counter(m["primary_tag"] for m in memories)

    # Pass 2: re-route memories whose provisional cluster is too small
    for m in memories:
        if provisional[m["primary_tag"]] >= min_cluster_size:
            continue
        # Try later candidates in frequency order; require the candidate's
        # cluster to be non-singleton
        cands = candidate_tags(m.get("tags", []))
        cands.sort()
        cands.sort(key=lambda t: freq.get(t, 0), reverse=True)
        new_tag = None
        for t in cands:
            if provisional.get(t, 0) >= min_cluster_size and t != m["primary_tag"]:
                new_tag = t
                break
        if new_tag:
            provisional[m["primary_tag"]] -= 1
            m["primary_tag"] = new_tag
            provisional[new_tag] += 1
        else:
            provisional[m["primary_tag"]] -= 1
            m["primary_tag"] = "_misc"
            provisional["_misc"] += 1

    # Group
    buckets: dict[str, list[dict]] = defaultdict(list)
    for m in memories:
        buckets[m["primary_tag"]].append(m)

    # Sort each bucket newest-first
    for tag, items in buckets.items():
        items.sort(key=lambda m: m.get("created_at", ""), reverse=True)

    # Split oversized clusters
    final: dict[str, list[dict]] = {}
    for tag, items in buckets.items():
        if len(items) <= max_cluster_size:
            final[tag] = items
            continue
        chunks = [items[i:i + max_cluster_size]
                  for i in range(0, len(items), max_cluster_size)]
        for i, chunk in enumerate(chunks, 1):
            final[f"{tag}-{i}"] = chunk

    return final


# ─── Reporting ──────────────────────────────────────────────────────────────

def cluster_stats(buckets: dict[str, list[dict]]) -> dict:
    """Summary for the manifest."""
    sizes = [len(v) for v in buckets.values()]
    return {
        "cluster_count": len(buckets),
        "memory_count": sum(sizes),
        "min_size": min(sizes) if sizes else 0,
        "max_size": max(sizes) if sizes else 0,
        "singleton_clusters": sum(1 for s in sizes if s == 1),
    }
