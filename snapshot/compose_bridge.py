"""Generate the bridge table embedded in SKILL.md.

The bridge maps topic tag → memory reference file with theme labels. It
lives inside SKILL.md (not as a separate file) so Claude has the index
available the moment the skill activates, without an extra load.
"""

from __future__ import annotations
from collections import Counter


# Tags that aren't useful as theme descriptors — too generic or already
# implicit in the cluster's primary tag.
_THEME_TAG_SKIP = {
    "research", "analysis", "synthesis", "review", "calibration",
    "preference", "correction", "experience", "decision", "world",
    "procedure", "anomaly",
    "shipped", "completed", "merged", "closed", "deferred",
    "ai-research", "ai", "llm", "models", "model",
    "session-log", "session-summary",
    "improvement", "anti-pattern", "pattern",
}


def _theme_tags_for_cluster(memories: list[dict], primary_tag: str,
                            max_themes: int = 6) -> list[str]:
    """Most-frequent co-occurring tags across `memories`, excluding the
    primary tag and meta filler."""
    c: Counter = Counter()
    for m in memories:
        for t in m.get("tags", []):
            if t == primary_tag or t in _THEME_TAG_SKIP:
                continue
            # Skip date-shaped tags
            if t[:4].isdigit() and (len(t) == 4 or t[4] == "-"):
                continue
            c[t] += 1
    return [t for t, _ in c.most_common(max_themes)]


def compose_bridge_table(buckets: dict[str, list[dict]],
                         cluster_files: list[dict]) -> str:
    """Render the bridge as a markdown table — sorted by cluster size desc.

    `buckets` is the {primary_tag: [memories]} dict.
    `cluster_files` is from kb.write_kb (filename, tag, memory_count, sorted).
    """
    lines = [
        "| Memories | File | Primary tag | Themes |",
        "|---:|---|---|---|",
    ]
    for cf in cluster_files:
        tag = cf["tag"]
        filename = cf["filename"]
        count = cf["memory_count"]
        memories = buckets.get(tag, [])
        themes = _theme_tags_for_cluster(memories, tag)
        themes_str = ", ".join(f"`{t}`" for t in themes) if themes else "—"
        # `_misc` tags get italic display; real tags get code display
        tag_display = f"_{tag}_" if tag.startswith("_") else f"`{tag}`"
        lines.append(
            f"| {count} | `references/{filename}` | {tag_display} | {themes_str} |"
        )
    return "\n".join(lines)
