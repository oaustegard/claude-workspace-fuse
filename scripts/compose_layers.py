#!/usr/bin/env python3
"""Hub glue: read .claude/container-layers.json and drive the container-layer skill.

Usage:
    python3 scripts/compose_layers.py apply       # restore (or build) all layers per manifest
    python3 scripts/compose_layers.py hash        # print composite hash, no apply
    python3 scripts/compose_layers.py inspect     # show what would be composed

Resolves layer names to paths:
    "base"         -> layers/Containerfile
    "scientific"   -> layers/Containerfile.scientific
    "<other>"      -> layers/Containerfile.<other>

Back-compat: if .claude/container-layers.json doesn't exist but a root-level
Containerfile does, falls back to single-layer restore (legacy mode). Downstream
forks that haven't migrated keep working until they add a manifest.

Composite hash for drift detection: sha256(layer1_hash + "\\n" + layer2_hash + ...)
truncated to 16 chars — same shape as the skill's single-layer hashes so the
existing /tmp/.containerfile-hash plumbing in boot-ccotw.sh and rebuild-layer.sh
keeps working.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(
    os.environ.get("CLAUDE_PROJECT_DIR", str(Path(__file__).resolve().parent.parent))
).resolve()
MANIFEST = PROJECT_DIR / ".claude" / "container-layers.json"
LAYERS_DIR = PROJECT_DIR / "layers"
LEGACY_CONTAINERFILE = PROJECT_DIR / "Containerfile"
SKILL_DIR = Path("/tmp/_container_layer")
CACHE_REPO = os.environ.get("LAYER_CACHE_REPO", "oaustegard/claude-container-layers")
GH_TOKEN = os.environ.get("GH_TOKEN", "")


def _layer_path(name: str) -> Path:
    if name == "base":
        return LAYERS_DIR / "Containerfile"
    return LAYERS_DIR / f"Containerfile.{name}"


def _layer_name(path: Path) -> str:
    if path.name == "Containerfile":
        return "base"
    if path.name.startswith("Containerfile."):
        return path.name[len("Containerfile."):]
    return path.stem


def _read_manifest() -> tuple[list[Path], bool]:
    """Return (ordered Containerfile paths, is_legacy_fallback)."""
    if MANIFEST.exists():
        with open(MANIFEST) as f:
            m = json.load(f)
        names = m.get("layers") or []
        paths: list[Path] = []
        missing: list[str] = []
        for n in names:
            p = _layer_path(n)
            if p.exists():
                paths.append(p)
            else:
                missing.append(n)
        if missing:
            print(f"  ! Skipping layers without Containerfile in layers/: {missing}")
        return paths, False

    # Legacy back-compat: no manifest, but root Containerfile present
    if LEGACY_CONTAINERFILE.exists():
        return [LEGACY_CONTAINERFILE], True

    return [], False


def _cli(*args: str, capture: bool = False) -> str:
    # Pass GH_TOKEN via env, NOT --token argv. CalledProcessError stringifies
    # the full argv, so any failure with --token in argv leaks the PAT into
    # the rebuild log (which the UserPromptSubmit hook surfaces back into the
    # model's context). The skill's cli.py defaults --token to $GH_TOKEN.
    cmd = [
        sys.executable, "-m", "scripts.cli",
        "--repo", CACHE_REPO,
        *args,
    ]
    env = {**os.environ, "GH_TOKEN": GH_TOKEN}
    if capture:
        return subprocess.check_output(cmd, cwd=SKILL_DIR, env=env).decode().strip()
    subprocess.check_call(cmd, cwd=SKILL_DIR, env=env)
    return ""


def _composite_hash(paths: list[Path]) -> str:
    parts = [_cli("hash", str(p), capture=True) for p in paths]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


def cmd_apply() -> None:
    paths, legacy = _read_manifest()
    if not paths:
        print("No layers to compose (no manifest, no legacy Containerfile)")
        return

    if legacy:
        print(f"Legacy mode: restoring single {paths[0].name}")
        _cli("restore", str(paths[0]))
    elif len(paths) == 1:
        # Single named layer — use restore with --name for correct cache tag
        name = _layer_name(paths[0])
        print(f"Restoring single layer: {name}")
        _cli("restore", str(paths[0]), "--name", name)
    else:
        names = [_layer_name(p) for p in paths]
        print(f"Composing layers: {' → '.join(names)}")
        _cli("compose", *(str(p) for p in paths))

    h = _composite_hash(paths)
    Path("/tmp/.containerfile-hash").write_text(h)
    print(f"  Composite hash: {h}")


def cmd_hash() -> None:
    paths, _ = _read_manifest()
    if not paths:
        return
    print(_composite_hash(paths))


def cmd_inspect() -> None:
    paths, legacy = _read_manifest()
    if not paths:
        print("(no layers)")
        return
    mode = "legacy single-Containerfile" if legacy else "manifest-driven composition"
    print(f"Mode: {mode}")
    print(f"Cache repo: {CACHE_REPO}")
    print()
    for p in paths:
        name = _layer_name(p)
        h = _cli("hash", str(p), capture=True)
        tag = f"layer-{name}-{h}" if not legacy else f"layer-{h}"
        print(f"  {name:15s} {tag}  ({p.relative_to(PROJECT_DIR)})")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("apply", "hash", "inspect"):
        print(__doc__)
        sys.exit(2)
    {"apply": cmd_apply, "hash": cmd_hash, "inspect": cmd_inspect}[sys.argv[1]]()


if __name__ == "__main__":
    main()
