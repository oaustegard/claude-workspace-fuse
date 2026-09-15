"""Build a Muninn snapshot as a claude-skill.

Output layout:
    out_dir/
      muninn-snapshot/
        SKILL.md                  ← entry point: triggers + quick-load + bridge
        references/
          identity.md             ← full persona (voice, values, tensions, ...)
          operating.md            ← full operating imperatives + behavior
          craft.md                ← universal craft triggers
          memory-{tag}.md ...     ← memory clusters
    muninn-snapshot.zip            ← the skill packaged for download/install

Usage:
    from snapshot.build import build_snapshot
    result = build_snapshot(out_dir="/home/claude/snapshot-out")

    # or CLI:
    python3 -m snapshot.build --out /home/claude/snapshot-out
"""

from __future__ import annotations
import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .config import MEMORY_TYPES_KEEP, MEMORY_MIN_PRIORITY
from .pull import pull_profile, pull_ops, pull_ops_topics, pull_memories
from .filter import (
    filter_memories_by_tag,
    redact_and_filter_memories,
)
from .cluster import cluster_by_primary_tag, cluster_stats
from .compose_instruction import (
    compose_skill_md,
    compose_craft_md,
)
from .compose_bridge import compose_bridge_table
from .kb import write_kb


SKILL_NAME = "muninn-snapshot"


def build_snapshot(out_dir: str | Path = "/home/claude/snapshot-out") -> dict:
    """End-to-end snapshot build. Returns paths + stats dict."""
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    skill_dir = out_dir / SKILL_NAME
    skill_dir.mkdir()
    refs_dir = skill_dir / "references"
    refs_dir.mkdir()

    # ── 1. Pull from DB ────────────────────────────────────────────────────
    profile_rows = pull_profile()
    ops_rows = pull_ops()
    ops_topics = pull_ops_topics()
    raw_memories = pull_memories(
        types=MEMORY_TYPES_KEEP,
        min_priority=MEMORY_MIN_PRIORITY,
    )

    pull_stats = {
        "profile_rows": len(profile_rows),
        "ops_rows": len(ops_rows),
        "raw_memories": len(raw_memories),
    }

    # ── 2. Filter + redact memories ─────────────────────────────────────────
    tag_kept, tag_dropped = filter_memories_by_tag(raw_memories)
    body_kept, body_drop_stats = redact_and_filter_memories(tag_kept)

    filter_stats = {
        "dropped_by_tag": tag_dropped,
        **body_drop_stats,
        "memories_kept": len(body_kept),
    }

    # ── 3. Cluster by primary tag ───────────────────────────────────────────
    buckets = cluster_by_primary_tag(body_kept)
    cluster_summary = cluster_stats(buckets)

    # ── 4. Write memory cluster files to references/ ────────────────────────
    written = write_kb(buckets, refs_dir)

    # ── 5. Compose references/craft.md (the only on-demand persona ref) ─────
    craft_text, craft_keys = compose_craft_md(ops_rows)
    (refs_dir / "craft.md").write_text(craft_text, encoding="utf-8")

    # ── 6. Compose SKILL.md with identity + operating inlined ──────────────
    bridge_table = compose_bridge_table(buckets, written)
    skill_text, included_keys = compose_skill_md(
        profile_rows,
        ops_rows,
        cluster_count=cluster_summary["cluster_count"],
        memory_count=cluster_summary["memory_count"],
        bridge_table=bridge_table,
    )
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(skill_text, encoding="utf-8")

    # ── 7. Zip the skill directory ──────────────────────────────────────────
    # Write the archive OUTSIDE out_dir so make_archive's walk doesn't pick
    # up a stale copy. Also delete any pre-existing zip — make_archive
    # silently fails to overwrite when the target was created by a
    # different user.
    zip_base = out_dir.parent / SKILL_NAME
    stale_zip = zip_base.with_suffix(".zip")
    if stale_zip.exists():
        try:
            stale_zip.unlink()
        except (OSError, PermissionError) as e:
            print(f"WARNING: could not remove stale zip {stale_zip}: {e}")
    zip_path = shutil.make_archive(
        str(zip_base),
        "zip",
        root_dir=out_dir,
        base_dir=SKILL_NAME,
    )

    stats = {
        **pull_stats,
        **filter_stats,
        **cluster_summary,
        "skill_chars": len(skill_text),
        "skill_lines": skill_text.count("\n") + 1,
        "craft_chars": len(craft_text),
    }

    return {
        "out_dir": str(out_dir),
        "skill_dir": str(skill_dir),
        "skill_path": str(skill_path),
        "refs_dir": str(refs_dir),
        "zip_path": zip_path,
        "stats": stats,
        "included_keys": {
            **included_keys,
            "craft": craft_keys,
        },
    }


# ─── CLI ────────────────────────────────────────────────────────────────────

def _cli():
    p = argparse.ArgumentParser(
        description="Build a Muninn snapshot as a claude-skill."
    )
    p.add_argument(
        "--out",
        default="/home/claude/snapshot-out",
        help="Output directory (default: /home/claude/snapshot-out)",
    )
    args = p.parse_args()
    result = build_snapshot(args.out)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    _cli()
