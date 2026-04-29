#!/usr/bin/env python3
"""PostToolUse hook for Bash: trim verbose tool output before it enters context.

Several tools (gh, git, find, tree) routinely emit thousands of lines of
output where only a small head/tail is meaningful. Claude Code v2.1.121
generalized `hookSpecificOutput.updatedToolOutput` to all tools, so a
PostToolUse hook can intercept Bash output and substitute a trimmed
version.

Trimming rules (issue #41):
  - `gh ... --json` JSON arrays >10KB        → head+tail of 50 entries each
  - `git log` / `git diff` >500 lines        → first 200 lines + marker
  - `find` / `tree` >2000 lines              → first 500 lines + marker

If no rule matches, the hook exits silently and the original output passes
through unchanged. When trimming fires, a visible marker is always inserted
so the dropped data is recoverable on demand.

Reads PostToolUse JSON from stdin. Always exits 0 to avoid breaking the
session — a crash here must never block tool flow.
"""
from __future__ import annotations

import json
import re
import sys

GH_JSON_BYTES_THRESHOLD = 10_000
GIT_LINE_THRESHOLD = 500
GIT_KEEP_LINES = 200
TREE_FIND_LINE_THRESHOLD = 2000
TREE_FIND_KEEP_LINES = 500
JSON_KEEP_ENTRIES = 50


def _is_gh_json(command: str) -> bool:
    return bool(re.search(r"\bgh\b[^|;&]*--json\b", command))


def _is_git_log_or_diff(command: str) -> bool:
    return bool(re.search(r"\bgit\s+(log|diff)\b", command))


def _is_tree_or_find(command: str) -> bool:
    return bool(re.search(r"(?:^|\||;|&&|\bnohup\b|\btime\b)\s*(tree|find)\b", command))


def _trim_gh_json(stdout: str) -> str | None:
    text = stdout.strip()
    if not text.startswith("["):
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list) or len(data) <= 2 * JSON_KEEP_ENTRIES:
        return None
    head = data[:JSON_KEEP_ENTRIES]
    tail = data[-JSON_KEEP_ENTRIES:]
    dropped = len(data) - 2 * JSON_KEEP_ENTRIES
    return (
        json.dumps(head, indent=2)
        + f"\n\n[... {dropped} entries dropped by trim-tool-output hook; "
        f"re-run with a tighter --limit or filter for full output ...]\n\n"
        + json.dumps(tail, indent=2)
    )


def _trim_by_lines(text: str, threshold: int, keep: int, label: str) -> str | None:
    lines = text.splitlines()
    if len(lines) <= threshold:
        return None
    dropped = len(lines) - keep
    marker = (
        f"[... {dropped} more lines dropped by trim-tool-output hook; "
        f"narrow the {label} command for full output ...]"
    )
    return "\n".join(lines[:keep] + [marker])


def _trim(command: str, stdout: str) -> str | None:
    if _is_gh_json(command) and len(stdout) > GH_JSON_BYTES_THRESHOLD:
        out = _trim_gh_json(stdout)
        if out is not None:
            return out
    if _is_git_log_or_diff(command):
        out = _trim_by_lines(stdout, GIT_LINE_THRESHOLD, GIT_KEEP_LINES, "git")
        if out is not None:
            return out
    if _is_tree_or_find(command):
        out = _trim_by_lines(
            stdout, TREE_FIND_LINE_THRESHOLD, TREE_FIND_KEEP_LINES, "tree/find"
        )
        if out is not None:
            return out
    return None


def _render(stdout: str, stderr: str, interrupted: bool) -> str:
    parts = []
    if stdout:
        parts.append(stdout)
        if not stdout.endswith("\n"):
            parts.append("\n")
    if stderr:
        parts.append(stderr)
        if not stderr.endswith("\n"):
            parts.append("\n")
    if interrupted:
        parts.append("[command interrupted]\n")
    return "".join(parts)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    if data.get("tool_name") != "Bash":
        return 0

    tool_input = data.get("tool_input") or {}
    command = tool_input.get("command") or ""

    response = data.get("tool_response") or {}
    stdout = response.get("stdout") or ""
    stderr = response.get("stderr") or ""
    interrupted = bool(response.get("interrupted"))

    trimmed = _trim(command, stdout)
    if trimmed is None:
        return 0

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "updatedToolOutput": _render(trimmed, stderr, interrupted),
            }
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
