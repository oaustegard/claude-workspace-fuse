#!/usr/bin/env python3
"""Build .well-known/tools.json — an agent-discoverable index of Muninn's
install-manifest surface.

Walks manifests/*/*.json, reads each manifest, and emits a JSON document
shaped per muninn-tools-index/v1. When several manifest versions of the same
tool coexist on disk (e.g. v0.3 kept for version-pinned installs alongside the
current v0.4), the index surfaces only the latest:

    {
      "schema_version": "muninn-tools-index/v1",
      "generated_at": "<ISO-8601 UTC>",
      "tools": [
        {
          "id": "...",
          "summary": "...",
          "manifest_url": "https://raw.githubusercontent.com/.../<path>",
          "manifest_version": "0.3",
          "tags": ["..."]
        },
        ...
      ]
    }

Output is sorted by tool id for stable diffs. Schema-violating manifests
abort the build — silent skips would mask the drift this index exists to
detect.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

SCHEMA_VERSION = "muninn-tools-index/v1"
RAW_BASE = (
    "https://raw.githubusercontent.com/oaustegard/muninn-utilities/main"
)


def _manifest_url(rel: Path) -> str:
    return f"{RAW_BASE}/{rel.as_posix()}"


def _version_key(manifest_version: str) -> tuple[int, ...]:
    """Sortable key for a dotted manifest_version like '0.4' or '0.10'."""
    try:
        return tuple(int(part) for part in str(manifest_version).split("."))
    except ValueError as exc:
        raise ValueError(
            f"unparseable manifest_version {manifest_version!r}: {exc}"
        ) from exc


def _entry(manifest_path: Path, repo_root: Path) -> dict:
    with manifest_path.open() as f:
        manifest = json.load(f)

    tool = manifest.get("tool") or {}
    tool_id = tool.get("id")
    summary = tool.get("summary")
    tags = tool.get("tags") or []
    manifest_version = manifest.get("manifest_version")

    missing = [
        k
        for k, v in (
            ("tool.id", tool_id),
            ("tool.summary", summary),
            ("manifest_version", manifest_version),
        )
        if not v
    ]
    if missing:
        raise ValueError(
            f"{manifest_path}: missing required field(s): {', '.join(missing)}"
        )

    expected_filename = manifest_path.name
    if not expected_filename.startswith(f"{tool_id}."):
        raise ValueError(
            f"{manifest_path}: filename does not start with tool.id "
            f"({tool_id!r}); index would mismatch the manifest"
        )

    rel = manifest_path.relative_to(repo_root)
    return {
        "id": tool_id,
        "summary": summary,
        "manifest_url": _manifest_url(rel),
        "manifest_version": manifest_version,
        "tags": list(tags),
    }


def build_index(repo_root: Path) -> dict:
    manifests_dir = repo_root / "manifests"
    if not manifests_dir.is_dir():
        raise FileNotFoundError(f"no manifests/ directory at {manifests_dir}")

    # One entry per tool.id, keeping the highest manifest_version. Multiple
    # versions of a tool legitimately coexist on disk during a schema
    # migration; the index lists only the current one. Two manifests sharing
    # both tool.id AND manifest_version is a genuine collision and still
    # aborts — that's the drift this index exists to detect.
    best: dict[str, tuple[tuple[int, ...], Path, dict]] = {}
    for subdir in sorted(p for p in manifests_dir.iterdir() if p.is_dir()):
        for manifest_path in sorted(subdir.glob("*.json")):
            entry = _entry(manifest_path, repo_root)
            version = _version_key(entry["manifest_version"])
            existing = best.get(entry["id"])
            if existing is not None:
                existing_version, existing_path, _ = existing
                if version == existing_version:
                    raise ValueError(
                        f"{manifest_path}: duplicate tool.id {entry['id']!r} "
                        f"at manifest_version {entry['manifest_version']!r} "
                        f"(also defined in {existing_path})"
                    )
                if version < existing_version:
                    continue
            best[entry["id"]] = (version, manifest_path, entry)

    entries = [entry for _, _, entry in best.values()]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "tools": sorted(entries, key=lambda e: e["id"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=os.fspath(Path(__file__).resolve().parents[1]),
        help="muninn-utilities repo root (default: parent of this script)",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="output path, or '-' for stdout (default: -)",
    )
    args = parser.parse_args(argv)

    index = build_index(Path(args.root))
    text = json.dumps(index, indent=2, ensure_ascii=False) + "\n"

    if args.output == "-":
        sys.stdout.write(text)
    else:
        Path(args.output).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
