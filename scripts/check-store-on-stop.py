#!/usr/bin/env python3
"""Stop hook: block end-of-turn when analysis-shaped output was produced
from external content but no remember() call was made.

Heuristic (all three must fire to block):
  1. The final assistant text in the turn is >= MIN_WORDS words.
  2. The turn fetched external content (WebFetch, WebSearch, mcp__github__*,
     bsky.py, gh pr/issue/release view, browsing-bluesky import, or
     curl/wget/httpx/requests against an http(s) URL).
  3. No remember() call appears in any Bash command this turn.

On block: exit 2 with a stderr message. Claude Code surfaces stderr to the
model and re-runs generation, so the model gets a structural nudge to store
before the turn actually ends. If the model replies and calls Stop again,
stop_hook_active is set and we pass through (no loop).

Reads Stop hook JSON from stdin. Always safe to crash silently with exit 0.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

MIN_WORDS = 200

# Tool names that imply external content
EXTERNAL_TOOLS = {"WebFetch", "WebSearch"}
EXTERNAL_TOOL_PREFIXES = ("mcp__github__",)

# Bash command patterns that imply external fetch
EXTERNAL_BASH_PATTERNS = [
    re.compile(r"\bbsky\.py\b"),
    re.compile(r"\bbrowsing[_-]bluesky\b"),
    re.compile(r"\bget_thread\b"),
    re.compile(r"\bgh\s+(pr|issue|release|repo|api)\s+(view|list|read|get)\b"),
    re.compile(r"\b(curl|wget)\b[^|;&]*\bhttps?://"),
    re.compile(r"\b(httpx|requests)\.(get|post)\s*\("),
    re.compile(r"\barxiv\.org\b"),
]

# Indicates remember() was called
REMEMBER_PATTERN = re.compile(r"\bremember\s*\(")


def _load_records(transcript_path: Path) -> list[dict]:
    records = []
    with transcript_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _last_turn_segments(records: list[dict]) -> tuple[str, list[dict]]:
    """Return (final_assistant_text, tool_uses_in_turn) for the most recent
    turn. A turn starts at the last user-string message (real prompt, not a
    tool_result) and runs to the end of the transcript."""
    turn_start = 0
    for i, r in enumerate(records):
        if r.get("type") != "user":
            continue
        content = (r.get("message") or {}).get("content")
        if isinstance(content, str) and content.strip():
            turn_start = i

    final_text_parts: list[str] = []
    tool_uses: list[dict] = []
    for r in records[turn_start:]:
        if r.get("type") != "assistant":
            continue
        content = (r.get("message") or {}).get("content") or []
        if not isinstance(content, list):
            continue
        for c in content:
            ct = c.get("type")
            if ct == "text":
                final_text_parts.append(c.get("text", ""))
            elif ct == "tool_use":
                tool_uses.append(c)

    return "\n".join(final_text_parts), tool_uses


def _is_external_tool_use(tu: dict) -> bool:
    name = tu.get("name", "")
    if name in EXTERNAL_TOOLS:
        return True
    if any(name.startswith(p) for p in EXTERNAL_TOOL_PREFIXES):
        return True
    if name == "Bash":
        cmd = (tu.get("input") or {}).get("command", "")
        return any(p.search(cmd) for p in EXTERNAL_BASH_PATTERNS)
    return False


def _has_remember_call(tool_uses: list[dict]) -> bool:
    for tu in tool_uses:
        if tu.get("name") != "Bash":
            continue
        cmd = (tu.get("input") or {}).get("command", "")
        if REMEMBER_PATTERN.search(cmd):
            return True
    return False


def _evaluate(transcript_path: Path) -> str | None:
    """Return a block message if the heuristic fires, else None."""
    records = _load_records(transcript_path)
    if not records:
        return None

    text, tool_uses = _last_turn_segments(records)
    word_count = len(text.split())
    if word_count < MIN_WORDS:
        return None

    external_uses = [tu for tu in tool_uses if _is_external_tool_use(tu)]
    if not external_uses:
        return None

    if _has_remember_call(tool_uses):
        return None

    counts: dict[str, int] = {}
    for tu in external_uses:
        name = tu.get("name", "?")
        if name == "Bash":
            cmd = (tu.get("input") or {}).get("command", "")
            for p in EXTERNAL_BASH_PATTERNS:
                m = p.search(cmd)
                if m:
                    name = f"Bash:{m.group(0)}"
                    break
        counts[name] = counts.get(name, 0) + 1
    sources = ", ".join(f"{k}×{v}" for k, v in sorted(counts.items()))
    return (
        f"Stop blocked by check-store-on-stop hook.\n"
        f"This turn produced ~{word_count}-word analysis sourced from external "
        f"content but no remember() call was made.\n"
        f"External fetches: {sources}\n"
        f"If the analysis is worth keeping, call remember(...) before ending. "
        f"If not (trivial summary, ephemeral chatter), reply with one short "
        f"line saying so — Stop will pass on the next iteration."
    )


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    if data.get("stop_hook_active"):
        return 0

    transcript = data.get("transcript_path") or ""
    if not transcript:
        return 0
    path = Path(transcript)
    if not path.is_file():
        return 0

    try:
        msg = _evaluate(path)
    except Exception:
        return 0

    if not msg:
        return 0

    if os.environ.get("CHECK_STORE_DRY_RUN") == "1":
        sys.stderr.write(msg + "\n")
        return 0

    sys.stderr.write(msg + "\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
