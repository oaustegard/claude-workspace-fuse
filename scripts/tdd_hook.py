#!/usr/bin/env python3
"""TDD enforcement hook (issue #69).

Two subcommands invoked from `.claude/settings.json`:

  posttooluse  After Edit/Write of an impl file in a configured TDD path,
               run the paired test file and surface its output as
               additionalContext on the next agent turn. Failure is signal,
               not a block — the agent reads the output and reacts.

  pretooluse   Before a Bash `git commit` runs, scan staged changes. If any
               impl file in a TDD-default path lacks a paired test change,
               deny the commit. Override: `tdd-skip: <reason>` line anywhere
               in the commit command.

Both subcommands no-op silently when `.claude/tdd-config.json` is absent
in the working directory, so opt-in is per-repo.

Config schema (`.claude/tdd-config.json`):
    {
      "tdd_default_paths": ["src/", "remembering/"],
      "tdd_skip_paths":    ["docs/", "scripts/oneshot/"],
      "test_mapping": [
        {"impl": "src/(.+)\\.py$", "test": "tests/test_$1.py"}
      ]
    }
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

CONFIG_PATH = Path(".claude/tdd-config.json")
TEST_TIMEOUT_SECONDS = 60
MAX_OUTPUT_BYTES = 8000

TDD_SKIP_RE = re.compile(r"tdd-skip:\s*\S", re.IGNORECASE)
GIT_COMMIT_RE = re.compile(r"\bgit\s+commit\b")


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config(cwd: Path) -> dict | None:
    """Load .claude/tdd-config.json relative to cwd, or None if absent."""
    path = cwd / CONFIG_PATH
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _normalize_paths(paths: Iterable[str]) -> list[str]:
    """Strip leading './' and ensure trailing '/' for prefix matching."""
    out = []
    for p in paths:
        p = p.strip()
        if p.startswith("./"):
            p = p[2:]
        if p and not p.endswith("/"):
            p = p + "/"
        if p:
            out.append(p)
    return out


# ---------------------------------------------------------------------------
# File classification
# ---------------------------------------------------------------------------

def is_test_file(path: str) -> bool:
    """Heuristic: a file is a test if its basename or directory says so."""
    parts = path.split("/")
    base = parts[-1]
    if base.startswith("test_") or base.endswith("_test.py"):
        return True
    if ".test." in base or ".spec." in base:
        return True
    if any(p in ("tests", "test", "__tests__", "spec") for p in parts[:-1]):
        return True
    return False


def in_any_path(file_path: str, prefixes: list[str]) -> bool:
    return any(file_path.startswith(p) for p in prefixes)


def expected_test_for(file_path: str, mappings: list[dict]) -> str | None:
    """Apply the first matching impl→test mapping, or None if no match."""
    for m in mappings:
        impl_pat = m.get("impl")
        test_tpl = m.get("test")
        if not impl_pat or not test_tpl:
            continue
        try:
            if re.match(impl_pat, file_path):
                return re.sub(impl_pat, test_tpl, file_path)
        except re.error:
            continue
    return None


# ---------------------------------------------------------------------------
# Test runner (PostToolUse)
# ---------------------------------------------------------------------------

def runner_for(test_path: Path) -> list[str] | None:
    """Pick a test runner command for the given test file, or None."""
    suffix = test_path.suffix.lower()
    if suffix == ".py":
        if shutil.which("pytest"):
            return ["pytest", "-x", "-q", str(test_path)]
        return [sys.executable, "-m", "unittest", "-q", str(test_path)]
    if suffix in (".js", ".mjs", ".cjs", ".ts"):
        if shutil.which("node"):
            return ["node", "--test", str(test_path)]
        return None
    if suffix == ".mojo":
        if shutil.which("mojo"):
            return ["mojo", "test", str(test_path)]
        return None
    return None


def run_tests(test_path: Path, cwd: Path) -> str:
    """Run the test command and return a trimmed transcript."""
    cmd = runner_for(test_path)
    if cmd is None:
        return f"[tdd-hook] {test_path}: no runner for this file type"
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return f"[tdd-hook] {test_path}: TIMEOUT after {TEST_TIMEOUT_SECONDS}s"
    except FileNotFoundError as e:
        return f"[tdd-hook] {test_path}: runner not found: {e}"

    status = "PASS" if proc.returncode == 0 else f"FAIL (exit {proc.returncode})"
    body = (proc.stdout or "") + (proc.stderr or "")
    if len(body) > MAX_OUTPUT_BYTES:
        body = body[:MAX_OUTPUT_BYTES] + f"\n[... truncated {len(body) - MAX_OUTPUT_BYTES} bytes ...]"
    return f"[tdd-hook] {test_path}: {status}\n{body.rstrip()}"


def posttooluse(payload: dict, cwd: Path) -> dict | None:
    """Return PostToolUse hookSpecificOutput dict, or None to no-op."""
    if payload.get("tool_name") not in ("Edit", "Write"):
        return None

    config = load_config(cwd)
    if config is None:
        return None

    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not file_path:
        return None

    rel = file_path
    cwd_str = str(cwd) + "/"
    if rel.startswith(cwd_str):
        rel = rel[len(cwd_str):]
    rel = rel.lstrip("./")

    if is_test_file(rel):
        return None

    skip_paths = _normalize_paths(config.get("tdd_skip_paths", []))
    if in_any_path(rel, skip_paths):
        return None

    default_paths = _normalize_paths(config.get("tdd_default_paths", []))
    if default_paths and not in_any_path(rel, default_paths):
        return None

    expected = expected_test_for(rel, config.get("test_mapping", []))
    if not expected:
        return None

    test_path = cwd / expected
    if not test_path.is_file():
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"[tdd-hook] {expected}: MISSING — paired test for "
                    f"{rel} does not exist yet (RED phase: write it next)"
                ),
            }
        }

    output = run_tests(test_path, cwd)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": output,
        }
    }


# ---------------------------------------------------------------------------
# Commit gate (PreToolUse)
# ---------------------------------------------------------------------------

def staged_files(cwd: Path) -> list[str]:
    """Return paths of staged files (added/modified/copied/renamed)."""
    try:
        proc = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def find_violations(files: list[str], config: dict) -> list[tuple[str, str]]:
    """Return [(impl, expected_test), ...] for impl-without-test changes."""
    skip_paths = _normalize_paths(config.get("tdd_skip_paths", []))
    default_paths = _normalize_paths(config.get("tdd_default_paths", []))
    mappings = config.get("test_mapping", [])
    staged = set(files)

    violations: list[tuple[str, str]] = []
    for f in files:
        if is_test_file(f):
            continue
        if in_any_path(f, skip_paths):
            continue
        if default_paths and not in_any_path(f, default_paths):
            continue
        expected = expected_test_for(f, mappings)
        if not expected:
            continue
        if expected not in staged:
            violations.append((f, expected))
    return violations


def pretooluse(payload: dict, cwd: Path) -> dict | None:
    """Return PreToolUse hookSpecificOutput dict to deny, or None to allow."""
    if payload.get("tool_name") != "Bash":
        return None

    command = (payload.get("tool_input") or {}).get("command") or ""
    if not GIT_COMMIT_RE.search(command):
        return None

    config = load_config(cwd)
    if config is None:
        return None

    if TDD_SKIP_RE.search(command):
        return None

    files = staged_files(cwd)
    if not files:
        return None

    violations = find_violations(files, config)
    if not violations:
        return None

    lines = [
        "[tdd-hook] commit blocked: impl files in TDD paths lack paired test changes.",
        "",
    ]
    for impl, test in violations:
        lines.append(f"  - {impl}  →  needs  {test}")
    lines += [
        "",
        "Resolutions (pick one):",
        "  1. Stage the corresponding test files alongside the impl change.",
        "  2. Add a `tdd-skip: <reason>` line to the commit body to bypass.",
        "",
        "Config: .claude/tdd-config.json",
    ]
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "\n".join(lines),
        }
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in ("posttooluse", "pretooluse"):
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    cwd_str = payload.get("cwd") or os.getcwd()
    cwd = Path(cwd_str)

    try:
        if argv[1] == "posttooluse":
            result = posttooluse(payload, cwd)
        else:
            result = pretooluse(payload, cwd)
    except Exception as e:
        sys.stderr.write(f"[tdd-hook] internal error: {e}\n")
        return 0

    if result is None:
        return 0
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
