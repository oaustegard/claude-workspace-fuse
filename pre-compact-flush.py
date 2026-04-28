#!/usr/bin/env python3
"""PreCompact hook: capture a checkpoint of recent context before compaction.

Compaction trims the model's context window but leaves the on-disk transcript
intact. Without a checkpoint, the post-compaction model loses its working
state — half-formed plans, unsaved decisions, "what was I about to do" —
even though the raw turns survive on disk.

This hook extracts a compact summary of the most recent activity (user
prompts, assistant action lines, files edited) and stores it as a memory
tagged `compaction-checkpoint`. A future session can recall it as a
breadcrumb. The hook always exits 0 — never blocks compaction.

Reads hook JSON from stdin. Expected fields: transcript_path, session_id.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RECENT_LINES = 40
MAX_PROMPTS = 5
MAX_ACTIONS = 8
MAX_FILES = 10
PROMPT_TRUNC = 240
ACTION_TRUNC = 160
SYSTEM_TAG_PREFIXES = ("<system-reminder", "<command-name", "<command-message",
                       "<command-args", "<local-command-stdout", "<bash-stdout",
                       "<bash-stderr", "Caveat:")


def _looks_like_system(text: str) -> bool:
    s = text.lstrip()
    return any(s.startswith(p) for p in SYSTEM_TAG_PREFIXES)


def _extract_user_text(content) -> str | None:
    if isinstance(content, str):
        return content if not _looks_like_system(content) else None
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                text = (block.get("text") or "").strip()
                if text and not _looks_like_system(text):
                    return text
    return None


def _extract_assistant_blocks(content):
    """Return (first_text_line, list of (tool_name, file_path|None))."""
    text_line = None
    tools = []
    if not isinstance(content, list):
        return text_line, tools
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text" and text_line is None:
            text = (block.get("text") or "").strip()
            if text:
                text_line = text.split("\n", 1)[0]
        elif btype == "tool_use":
            tool = block.get("name", "")
            inp = block.get("input") or {}
            fp = inp.get("file_path") if isinstance(inp, dict) else None
            tools.append((tool, fp))
    return text_line, tools


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        return 0

    transcript_path = hook_input.get("transcript_path")
    session_id = hook_input.get("session_id", "unknown")

    if not transcript_path:
        return 0
    p = Path(transcript_path)
    if not p.exists():
        return 0

    try:
        with p.open() as f:
            lines = f.readlines()
    except Exception:
        return 0

    user_prompts: list[str] = []
    actions: list[str] = []
    files_edited: list[str] = []

    for line in lines[-RECENT_LINES:]:
        try:
            entry = json.loads(line)
        except Exception:
            continue
        msg = entry.get("message") or {}
        role = msg.get("role")
        content = msg.get("content")

        if role == "user":
            text = _extract_user_text(content)
            if text:
                user_prompts.append(text[:PROMPT_TRUNC])
        elif role == "assistant":
            text_line, tools = _extract_assistant_blocks(content)
            if text_line:
                actions.append(text_line[:ACTION_TRUNC])
            for tool, fp in tools:
                if tool in ("Edit", "Write", "NotebookEdit") and fp:
                    files_edited.append(fp)
                elif tool and tool not in ("Edit", "Write", "NotebookEdit"):
                    actions.append(f"[{tool}]"[:ACTION_TRUNC])

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts = [
        f"Compaction checkpoint at {ts}",
        f"Session: {session_id}",
        "",
    ]
    if user_prompts:
        parts.append("Recent user prompts:")
        parts.extend(f"  - {p}" for p in user_prompts[-MAX_PROMPTS:])
        parts.append("")
    if actions:
        parts.append("Recent assistant actions:")
        parts.extend(f"  - {a}" for a in actions[-MAX_ACTIONS:])
        parts.append("")
    if files_edited:
        parts.append("Files edited recently:")
        parts.extend(f"  - {f}" for f in files_edited[-MAX_FILES:])

    content_out = "\n".join(parts)

    try:
        sys.path.insert(0, "/mnt/skills/user/remembering")
        from scripts import remember
        mid = remember(
            content_out,
            "experience",
            tags=["compaction-checkpoint", "auto", f"session-{session_id[:8]}"],
            priority=0,
            sync=True,
        )
        print(f"pre-compact-flush: stored {mid}", file=sys.stderr)
    except Exception as e:
        print(f"pre-compact-flush: failed ({e})", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
