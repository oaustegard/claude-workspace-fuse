"""Write knowledge-base cluster files.

One .md per cluster, frontmatter with tag + count + date range, memories
inside ordered newest-first.
"""

from __future__ import annotations
import re
from pathlib import Path


_SAFE_NAME = re.compile(r"[^a-z0-9._-]+")


def _safe_filename(tag: str) -> str:
    """Filesystem-safe name from a tag. Keep readable; lowercase; strip junk."""
    name = tag.lower().strip()
    name = _SAFE_NAME.sub("-", name)
    name = name.strip("-")
    return name or "untitled"


def _short_id(memory_id: str) -> str:
    return (memory_id or "")[:8]


_URL_REF = re.compile(r"^https?://")


def _filter_refs(refs_json: str) -> list[str]:
    """Refs are a JSON array; keep only safe ones."""
    if not refs_json:
        return []
    try:
        import json
        refs = json.loads(refs_json)
    except (ValueError, TypeError):
        return []

    out = []
    for r in refs:
        if not isinstance(r, str):
            continue
        # Drop personal-site URLs
        if any(host in r for host in (
            "muninn.austegard.com", "austegard.com", "aeyu.io",
            "bsky.app", "bsky.social", "yepgent.com",
        )):
            continue
        # Drop personal repo paths
        if "oaustegard/" in r:
            continue
        out.append(r)
    return out


def _format_memory(m: dict) -> str:
    """Render one memory as a heading block (enriched)."""
    date = (m.get("created_at") or "")[:10]
    body = m.get("body_redacted") or m.get("summary", "")
    full_id = m.get("id", "")
    short = full_id[:8]
    mtype = m.get("type", "")
    priority = m.get("priority", 0)
    tags = m.get("tags", [])
    primary = m.get("primary_tag")
    other_tags = [t for t in tags if t != primary]

    refs = _filter_refs(m.get("refs"))

    header = f"## {date} — {mtype} (p{priority}) `{short}`"
    parts = [header]
    if other_tags:
        parts.append(f"_tags: {', '.join(other_tags)}_")
    parts.append("")
    parts.append(body.strip())
    if refs:
        parts.append("")
        parts.append("**Refs:**")
        for r in refs:
            parts.append(f"- {r}")
    return "\n".join(parts)


def _format_cluster(tag: str, memories: list[dict]) -> str:
    """One full cluster file."""
    dates = sorted([m.get("created_at", "")[:10] for m in memories if m.get("created_at")])
    date_range = f"{dates[0]} to {dates[-1]}" if dates else "unknown"

    out = [
        "---",
        f"tag: {tag}",
        f"memory_count: {len(memories)}",
        f"date_range: {date_range}",
        "---",
        "",
        f"# {tag}",
        "",
        f"_{len(memories)} memories from Muninn's past, primary tag `{tag}`._",
        "",
    ]
    for m in memories:
        out.append(_format_memory(m))
        out.append("")
        out.append("---")
        out.append("")
    return "\n".join(out)


def write_kb(buckets: dict[str, list[dict]], out_dir: Path) -> list[dict]:
    """Write each cluster to `out_dir/memory-{safe-tag}.md`.

    Returns a list of {filename, tag, memory_count} dicts, sorted by size
    descending — used downstream by the bridge composer.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    seen_names: set[str] = set()

    # Sort by cluster size descending so the bridge reads largest-first
    for tag in sorted(buckets, key=lambda t: (-len(buckets[t]), t)):
        memories = buckets[tag]
        safe = _safe_filename(tag)
        name = f"memory-{safe}.md"
        # Disambiguate filename collisions if two different tags safe-name
        # to the same thing
        counter = 2
        while name in seen_names:
            name = f"memory-{safe}-{counter}.md"
            counter += 1
        seen_names.add(name)

        path = out_dir / name
        path.write_text(_format_cluster(tag, memories), encoding="utf-8")
        written.append({
            "filename": name,
            "tag": tag,
            "memory_count": len(memories),
        })
    return written



