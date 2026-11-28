"""ruff_gate — run Ruff against a branch and report only the violations it ADDED.

Ruff 0.16.0 (2026-07-23) enables 413 rules by default, up from 59. Existing
trees light up under the new defaults: muninn-utilities reports 589 violations
at 0.16.0 with zero configuration. A whole-tree pass/fail gate on that number
is noise, so it gets ignored, so it gates nothing.

This runs Ruff twice — once on the working tree, once on the same files as they
exist at the base ref — and diffs the per-file, per-rule counts. Pre-existing
violations are the baseline; only what this branch added is reported. The
legacy debt stays visible in `--statistics` without blocking work.

The Ruff version is PINNED. Simon Willison's CI broke the day 0.16.0 landed
because his dev dependency was an unpinned "ruff"; a gate that changes its own
rules underneath you is a gate that fails on unrelated pushes. Bump RUFF_SPEC
deliberately, run the gate, absorb the delta in its own commit.

Usage:
    from muninn_utils.ruff_gate import ruff_gate, report
    print(report(ruff_gate(base_ref="main", repo_root="/home/claude/repo")))

    python -m muninn_utils.ruff_gate --base main --repo .
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections import Counter

RUFF_SPEC = "ruff==0.16.0"


def _ruff_cmd() -> list[str]:
    """Prefer an installed ruff; fall back to uvx at the pinned version."""
    exe = shutil.which("ruff")
    if exe:
        return [exe]
    if shutil.which("uvx"):
        return ["uvx", RUFF_SPEC]
    raise RuntimeError("neither ruff nor uvx on PATH")


def _git(args: list[str], repo_root: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def changed_python_files(base_ref: str = "main", repo_root: str = ".") -> list[str]:
    """Python files differing between the working tree and base_ref.

    Uses `git diff <ref>`, so uncommitted edits count — that is the state a
    pre-push gate should be judging.
    """
    tracked = _git(["diff", "--name-only", "--diff-filter=ACMR", base_ref], repo_root)
    # Untracked files don't show in `git diff` and are exactly what most needs
    # linting — a brand-new module has no baseline, so every violation is new.
    untracked = _git(["ls-files", "--others", "--exclude-standard"], repo_root)
    names = set(tracked.split("\n")) | set(untracked.split("\n"))
    return sorted(p for p in names if p.endswith((".py", ".pyi")))


def _check(paths: list[str], cwd: str) -> list[dict]:
    """Ruff diagnostics as JSON. Missing paths are skipped, not fatal."""
    present = [p for p in paths if os.path.exists(os.path.join(cwd, p))]
    if not present:
        return []
    proc = subprocess.run(
        [*_ruff_cmd(), "check", "--output-format", "json", "--force-exclude", *present],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"ruff failed ({proc.returncode}): {proc.stderr.strip()[:400]}")
    return json.loads(proc.stdout or "[]")


def _baseline_tree(paths: list[str], base_ref: str, repo_root: str) -> str:
    """Materialise the base_ref version of `paths` into a temp dir."""
    tmp = tempfile.mkdtemp(prefix="ruff-baseline-")
    for path in paths:
        blob = subprocess.run(
            ["git", "show", f"{base_ref}:{path}"],
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
        if blob.returncode != 0:  # file is new on this branch
            continue
        dest = os.path.join(tmp, path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(blob.stdout)
    return tmp


def _key(diag: dict, root: str) -> tuple[str, str]:
    return (os.path.relpath(diag["filename"], root), diag.get("code") or "?")


def ruff_gate(
    base_ref: str = "main", paths: list[str] | None = None, repo_root: str = "."
) -> dict:
    """Diff Ruff violations between the working tree and base_ref.

    Returns {'new': [diagnostics], 'counts': {(file, code): (base, now)},
             'files': [...], 'baseline_total': int, 'current_total': int}.
    `new` is empty when the branch introduced nothing — that is the pass case.
    """
    repo_root = os.path.abspath(repo_root)
    files = paths if paths is not None else changed_python_files(base_ref, repo_root)
    if not files:
        return {"new": [], "counts": {}, "files": [], "baseline_total": 0, "current_total": 0}

    current = _check(files, repo_root)
    tmp = _baseline_tree(files, base_ref, repo_root)
    try:
        base = _check(files, tmp)
        base_counts = Counter(_key(d, tmp) for d in base)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    cur_counts = Counter(_key(d, repo_root) for d in current)
    added = {k: (base_counts.get(k, 0), n) for k, n in cur_counts.items() if n > base_counts.get(k, 0)}
    new = [d for d in current if _key(d, repo_root) in added]
    return {
        "new": new,
        "counts": added,
        "files": files,
        "baseline_total": len(base),
        "current_total": len(current),
    }


def report(result: dict, limit: int = 40) -> str:
    """Human-readable gate verdict. Empty `new` reads as PASS."""
    if not result["files"]:
        return "ruff_gate: no Python files changed — PASS"
    head = (
        f"ruff_gate ({RUFF_SPEC}): {len(result['files'])} file(s), "
        f"{result['baseline_total']} baseline -> {result['current_total']} current"
    )
    if not result["new"]:
        return f"{head}\nNo new violations — PASS"
    lines = [head, f"{len(result['new'])} NEW violation(s) — FAIL"]
    for diag in result["new"][:limit]:
        loc = diag.get("location") or {}
        lines.append(
            f"  {diag['filename']}:{loc.get('row')}:{loc.get('column')}: "
            f"{diag.get('code')} {diag.get('message')}"
        )
    if len(result["new"]) > limit:
        lines.append(f"  ... {len(result['new']) - limit} more")
    return "\n".join(lines)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Report Ruff violations added since a base ref.")
    ap.add_argument("--base", default="main")
    ap.add_argument("--repo", default=".")
    ap.add_argument("paths", nargs="*")
    args = ap.parse_args()
    result = ruff_gate(args.base, args.paths or None, args.repo)
    print(report(result))
    return 1 if result["new"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
