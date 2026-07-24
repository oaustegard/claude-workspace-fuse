"""
audit.py — boot-time install-manifest audit (oaustegard/muninn-utilities#6).

Walks `manifests/<utility>/muninn-<utility>.v0.3.json` plus `muninn_utils/*.py`
and reports drift between the declared install-manifest surface and the
actual code:

  1. Manifests parse as JSON. (Bad/missing → warn, never raise.)
  2. `env[].required: true` vars resolve to non-empty values in the boot
     environment. Unset → "unconfigured" warning, NOT a block.
  3. Env-var names referenced by the utility's source via os.environ /
     os.getenv match those declared in the manifest's env[]. Drift in
     either direction (used-not-declared, declared-not-used) → warn.
     Manifest entries with `indirect: true` opt out of drift checks
     in both directions (still subject to required-loadable check).
  4. The set of manifest directory names matches the set of module stem
     names under `muninn_utils/`. Diff in either direction → warn.

Warn-quiet by default (boot is timing-sensitive; a noisy audit failure
during a flight is worse than a missed warning). `audit(..., emit_to_stderr=True)`
opts in to stderr output — the boot wires this on.

Public surface:

  load_manifest(path) -> dict | None
  check_env_loadable(manifest, env) -> list[str]   # required-but-unset names
  detect_scope_drift(source, manifest) -> {"used_not_declared": [...],
                                           "declared_not_used": [...]}
  index_diff(manifest_dir, module_dir) -> {"manifests_only": [...],
                                           "modules_only": [...]}
  audit(manifest_dir, module_dir, env=None, emit_to_stderr=False) -> dict
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Optional


# Match os.environ.get("NAME"), os.environ["NAME"], os.getenv("NAME").
# All three forms; either quote style. NAME must look like a SCREAMING_SNAKE
# env var (start with letter/underscore, allow digits after).
_ENV_REF_RE = re.compile(
    r"""os\.environ\.get\(\s*['"]([A-Z_][A-Z0-9_]*)['"]"""
    r"""|os\.getenv\(\s*['"]([A-Z_][A-Z0-9_]*)['"]"""
    r"""|os\.environ\[\s*['"]([A-Z_][A-Z0-9_]*)['"]""",
)

# Modules under muninn_utils/ that aren't real utilities and shouldn't be
# audited as such. `flowing` is a thin re-export shim of the canonical
# /mnt/skills/user/flowing/scripts/flowing.py — it has no install surface
# of its own, so demanding a manifest for it produces a permanent false
# positive. The canonical flowing skill ships its own manifest.
_IGNORED_MODULES = {"__init__", "flowing"}


def load_manifest(path: str) -> Optional[dict]:
    """Read and parse a manifest JSON file. Returns None on any failure."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def check_env_loadable(manifest: dict, env: dict) -> list[str]:
    """Return the names of `required: true` env vars not present (or blank) in env.

    A var is "loadable" iff env contains a non-empty string for it.
    Optional vars are never reported.
    """
    missing = []
    for entry in manifest.get("env", []) or []:
        if not entry.get("required", True):
            continue
        name = entry.get("name")
        if not name:
            continue
        value = env.get(name, "")
        if not value:
            missing.append(name)
    return missing


def _extract_env_refs(source: str) -> set[str]:
    """Return the set of env-var names the source actually reads via os.environ/getenv."""
    found: set[str] = set()
    for m in _ENV_REF_RE.finditer(source):
        # Each alternative captures into a different group; take the one that matched.
        name = m.group(1) or m.group(2) or m.group(3)
        if name:
            found.add(name)
    return found


def detect_scope_drift(source: str, manifest: dict) -> dict:
    """Compare env-var refs in `source` against `manifest['env'][]`.

    Manifest entries with `indirect: true` are required by the utility but
    accessed transitively — via library calls (e.g. `_exec` reading TURSO_*
    inside the remembering library), via dynamic keys (`os.environ[arg_name]`),
    or via downstream modules loaded after `sys.path.insert`. The audit's
    static regex cannot see them, so they're excluded from the drift check
    in both directions: they don't trigger declared-not-used warnings, and
    they're not expected to appear as used-not-declared either.

    The required-env-loadable check (check_env_loadable) still applies to
    indirect entries — they must be set in the boot environment.

    Returns:
        {"used_not_declared": sorted list of names the source reads but the
                              manifest does not declare,
         "declared_not_used": sorted list of names the manifest declares but
                              the source never references (excluding indirect)}
    """
    declared = {
        e.get("name")
        for e in (manifest.get("env") or [])
        if e.get("name")
    }
    indirect = {
        e.get("name")
        for e in (manifest.get("env") or [])
        if e.get("indirect") is True and e.get("name")
    }
    used = _extract_env_refs(source)
    return {
        "used_not_declared": sorted(used - declared),
        "declared_not_used": sorted(declared - used - indirect),
    }


def _manifest_dirs(manifest_root: str) -> list[str]:
    """List subdirectory names under manifest_root that contain at least one .json."""
    if not os.path.isdir(manifest_root):
        return []
    out = []
    for name in sorted(os.listdir(manifest_root)):
        sub = os.path.join(manifest_root, name)
        if not os.path.isdir(sub):
            continue
        if name.startswith("_") or name.startswith("."):
            continue
        if any(f.endswith(".json") for f in os.listdir(sub)):
            out.append(name)
    return out


def _module_stems(module_root: str) -> list[str]:
    """List .py module stems directly under module_root (no recursion)."""
    if not os.path.isdir(module_root):
        return []
    out = []
    for name in sorted(os.listdir(module_root)):
        path = os.path.join(module_root, name)
        if not os.path.isfile(path):
            continue
        if not name.endswith(".py"):
            continue
        stem = name[:-3]
        if stem in _IGNORED_MODULES:
            continue
        out.append(stem)
    return out


def index_diff(manifest_dir: str, module_dir: str) -> dict:
    """Compare manifest-dir names against module stems.

    Manifest dir names use kebab-case (`bsky-card/`); modules use snake_case
    (`bsky_card.py`). Compare with `-` normalized to `_` so the two address
    spaces line up.
    """
    manifest_keys = {d.replace("-", "_") for d in _manifest_dirs(manifest_dir)}
    module_keys = set(_module_stems(module_dir))
    return {
        "manifests_only": sorted(manifest_keys - module_keys),
        "modules_only": sorted(module_keys - manifest_keys),
    }


_VERSIONED_MANIFEST_RE = re.compile(r"\.v(\d+)\.(\d+)\.json$")


def _find_manifest_file(sub: str) -> Optional[str]:
    """Return path to the newest-version `.vX.Y.json` (or any `.json`) inside `sub`.

    When both `muninn-foo.v0.3.json` and `muninn-foo.v0.4.json` exist, the
    audit must pick the newer one — v0.3 files are kept on disk for tooling
    pinned to that version but no longer represent the canonical install
    surface. Versions are compared as (major, minor) integer tuples; the
    largest wins. Unversioned `.json` files are only considered when no
    versioned file exists.
    """
    if not os.path.isdir(sub):
        return None
    versioned: list[tuple[tuple[int, int], str]] = []
    unversioned: list[str] = []
    for f in os.listdir(sub):
        if not f.endswith(".json"):
            continue
        m = _VERSIONED_MANIFEST_RE.search(f)
        if m:
            versioned.append(((int(m.group(1)), int(m.group(2))), f))
        else:
            unversioned.append(f)
    if versioned:
        versioned.sort(reverse=True)  # newest version first
        return os.path.join(sub, versioned[0][1])
    if unversioned:
        return os.path.join(sub, sorted(unversioned)[0])
    return None


def _read_module_source(module_dir: str, stem: str) -> Optional[str]:
    path = os.path.join(module_dir, f"{stem}.py")
    try:
        with open(path, "r") as f:
            return f.read()
    except OSError:
        return None


def audit(
    manifest_dir: str,
    module_dir: str,
    env: Optional[dict] = None,
    emit_to_stderr: bool = False,
) -> dict:
    """Run the full audit. Never raises.

    Returns:
        {"summary":  one-line audited-count summary,
         "warnings": list of human-readable warning strings,
         "by_utility": {<dir-name>: {"missing_env": [...], "drift": {...},
                                     "manifest_loaded": bool}},
         "index":    {"manifests_only": [...], "modules_only": [...]}}
    """
    if env is None:
        env = dict(os.environ)

    warnings: list[str] = []
    by_utility: dict[str, dict] = {}

    manifest_dirs = _manifest_dirs(manifest_dir)
    audited = 0
    missing_manifests: list[str] = []

    for udir in manifest_dirs:
        sub = os.path.join(manifest_dir, udir)
        path = _find_manifest_file(sub)
        if not path:
            warnings.append(f"[{udir}] no manifest .json file under {sub}")
            by_utility[udir] = {"manifest_loaded": False}
            continue

        manifest = load_manifest(path)
        if manifest is None:
            warnings.append(f"[{udir}] manifest at {path} did not parse as JSON")
            by_utility[udir] = {"manifest_loaded": False}
            continue

        audited += 1
        record: dict = {"manifest_loaded": True}

        missing_env = check_env_loadable(manifest, env)
        record["missing_env"] = missing_env
        if missing_env:
            warnings.append(
                f"[{udir}] required env unconfigured: {', '.join(missing_env)}"
            )

        # Scope drift: load matching module source. Manifest dir uses kebab-case;
        # module file uses snake_case.
        stem = udir.replace("-", "_")
        source = _read_module_source(module_dir, stem)
        if source is None:
            missing_manifests.append(udir)
            record["drift"] = None
        else:
            drift = detect_scope_drift(source, manifest)
            record["drift"] = drift
            if drift["used_not_declared"]:
                warnings.append(
                    f"[{udir}] env used by source but not declared in manifest: "
                    f"{', '.join(drift['used_not_declared'])}"
                )
            # `declared_not_used` is informational and retained on `record["drift"]`
            # for callers that want it, but no longer surfaces as a warning. The
            # `indirect: true` env extension that previously suppressed it has been
            # dropped because the install-manifest v0.4 schema rejects extension
            # fields on env[] entries.

        by_utility[udir] = record

    diff = index_diff(manifest_dir, module_dir)
    if diff["manifests_only"]:
        warnings.append(
            f"manifests with no module: {', '.join(diff['manifests_only'])}"
        )
    if diff["modules_only"]:
        warnings.append(
            f"modules with no manifest: {', '.join(diff['modules_only'])}"
        )

    total_modules = len(_module_stems(module_dir))
    summary = (
        f"manifest audit: {audited} of {total_modules} utilities manifested, "
        f"{len(warnings)} warnings"
    )

    if emit_to_stderr and warnings:
        for w in warnings:
            print(f"  ⚠ {w}", file=sys.stderr)

    return {
        "summary": summary,
        "warnings": warnings,
        "by_utility": by_utility,
        "index": diff,
    }


# CLI: `python -m scripts.audit <repo_root>` runs the audit against a
# checked-out muninn-utilities and prints the report.
if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    result = audit(
        os.path.join(root, "manifests"),
        os.path.join(root, "muninn_utils"),
        emit_to_stderr=True,
    )
    print(result["summary"])
    sys.exit(0)
