#!/usr/bin/env python3
"""Spoke-level container-layer overlay: apply extra layers declared by a spoke.

Usage:
    python3 scripts/apply_spoke_layers.py .spokes/<name>
    python3 scripts/apply_spoke_layers.py .spokes/<name> --inspect   # dry-run

A spoke (cloned into ``.spokes/<name>/``) may declare additional container
layers it needs on top of the hub composition. The manifest lives at
``.spokes/<name>/.claude/container-layers.json`` and uses an ``"extra"`` key
(distinct from the hub's ``"layers"`` key to make the additive intent
obvious):

    {"extra": ["julia-sr"]}

For each name in ``extra`` that is NOT already present in the hub manifest
(``.claude/container-layers.json`` at the workspace root), this script
resolves it to a Containerfile and invokes the container-layer skill's
``restore`` subcommand (per-layer; no recomposition of layers already
restored). Resolution order:

    1. ``<spoke>/layers/Containerfile.<name>``  (spoke-defined layer)
    2. ``<hub>/layers/Containerfile.<name>``    (hub-defined layer the
                                                 spoke just wants opted in)

Idempotent — re-running after all extras are present is a no-op. If the
spoke has no manifest, or ``extra`` is empty/absent, exits silently.

Design rationale: chose explicit invocation over a bash ``cd`` hook. Hooks
look automatic but are fragile (subshells skip bashrc; the Anthropic
container's bash_tool calls don't always source it). An agent that enters
a spoke can run this once; it costs ~30s for a cache hit and is a no-op
afterward. See PR body for the full trade-off discussion.
"""

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

# Import compose_layers as a sibling module (scripts/ isn't a package).
_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "compose_layers", _HERE / "compose_layers.py"
)
compose_layers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compose_layers)


def _read_hub_active_layers() -> list[str]:
    """Return ordered list of layer names currently declared in the hub manifest.

    Reads compose_layers.MANIFEST so tests that monkey-patch PROJECT_DIR /
    MANIFEST get picked up. Returns [] if the manifest is absent or has no
    ``layers`` key.
    """
    manifest_path = compose_layers.MANIFEST
    if not manifest_path.exists():
        return []
    with open(manifest_path) as f:
        m = json.load(f)
    return list(m.get("layers") or [])


def _read_spoke_manifest(spoke_dir: Path) -> list[str]:
    """Return ordered list of extra layer names declared by the spoke.

    Empty list if the manifest is absent or has no ``extra`` key.
    """
    manifest_path = spoke_dir / ".claude" / "container-layers.json"
    if not manifest_path.exists():
        return []
    with open(manifest_path) as f:
        m = json.load(f)
    return list(m.get("extra") or [])


def _resolve_layer_path(name: str, spoke_dir: Path) -> Path | None:
    """Find Containerfile for ``name``, preferring spoke-local over hub.

    Returns None if not found in either location.
    """
    # Spoke-local first — lets a spoke define its own layer entirely
    spoke_path = (
        spoke_dir / "layers" / "Containerfile"
        if name == "base"
        else spoke_dir / "layers" / f"Containerfile.{name}"
    )
    if spoke_path.exists():
        return spoke_path

    # Fall back to hub
    hub_path = compose_layers._layer_path(name)
    if hub_path.exists():
        return hub_path

    return None


def _compute_overlay(spoke_dir: Path) -> tuple[list[str], list[str], list[str]]:
    """Compute (to_apply, already_active, unresolved) for the given spoke.

    - to_apply: extras whose Containerfile resolves and that aren't already
      in the hub composition (preserves spoke manifest order, dedup'd).
    - already_active: extras that are already in the hub composition.
    - unresolved: extras whose Containerfile couldn't be found.
    """
    spoke_extras = _read_spoke_manifest(spoke_dir)
    hub_active = set(_read_hub_active_layers())

    to_apply: list[str] = []
    already_active: list[str] = []
    unresolved: list[str] = []
    seen: set[str] = set()

    for name in spoke_extras:
        if name in seen:
            continue
        seen.add(name)
        if name in hub_active:
            already_active.append(name)
            continue
        if _resolve_layer_path(name, spoke_dir) is None:
            unresolved.append(name)
            continue
        to_apply.append(name)

    return to_apply, already_active, unresolved


def cmd_apply(spoke_dir: Path) -> int:
    """Restore each missing spoke extra. Returns process exit code."""
    if not spoke_dir.is_dir():
        print(f"✗ Spoke dir not found: {spoke_dir}")
        return 2

    to_apply, already_active, unresolved = _compute_overlay(spoke_dir)

    if unresolved:
        print(
            f"  ! Spoke extras with no Containerfile in either "
            f"{spoke_dir}/layers/ or hub layers/: {unresolved}"
        )

    if not to_apply:
        if already_active:
            print(
                f"All spoke extras already active in hub composition: "
                f"{already_active}"
            )
        else:
            print(
                f"No spoke layers to apply (manifest absent, empty, or all "
                f"resolved layers already active)"
            )
        return 0

    if already_active:
        print(f"  Skipping already-active: {already_active}")

    print(f"Applying spoke extras: {to_apply}")
    for name in to_apply:
        path = _resolve_layer_path(name, spoke_dir)
        origin = "spoke" if path.is_relative_to(spoke_dir) else "hub"
        print(f"  → restore {name} (from {origin}: {path})")
        compose_layers._cli("restore", str(path), "--name", name)

    return 0


def cmd_inspect(spoke_dir: Path) -> int:
    """Show what would be applied without invoking the skill CLI."""
    if not spoke_dir.is_dir():
        print(f"✗ Spoke dir not found: {spoke_dir}")
        return 2

    spoke_extras = _read_spoke_manifest(spoke_dir)
    hub_active = _read_hub_active_layers()
    to_apply, already_active, unresolved = _compute_overlay(spoke_dir)

    print(f"Spoke dir:      {spoke_dir}")
    print(f"Spoke extras:   {spoke_extras or '(none)'}")
    print(f"Hub active:     {hub_active or '(none)'}")
    print(f"Would apply:    {to_apply or '(none)'}")
    print(f"Already active: {already_active or '(none)'}")
    if unresolved:
        print(f"Unresolved:     {unresolved}")

    for name in to_apply:
        path = _resolve_layer_path(name, spoke_dir)
        origin = "spoke" if path.is_relative_to(spoke_dir) else "hub"
        print(f"  {name:15s} {origin:5s}  {path}")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply spoke-level container-layer overlay."
    )
    parser.add_argument("spoke_dir", help="Path to spoke directory (e.g. .spokes/eml-sr)")
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Show what would be applied without invoking the skill CLI",
    )
    args = parser.parse_args()
    spoke_dir = Path(args.spoke_dir).resolve()
    rc = cmd_inspect(spoke_dir) if args.inspect else cmd_apply(spoke_dir)
    sys.exit(rc)


if __name__ == "__main__":
    main()
