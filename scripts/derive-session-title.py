#!/usr/bin/env python3
"""UserPromptSubmit hook: derive a semantic session title from the first prompt.

Emits hookSpecificOutput.sessionTitle (Claude Code v2.1.94+) and writes the
title to /tmp/.session-title-<session_id> so persist-transcript.sh can reuse it
when naming the GitHub release.

Gating: a marker file at /tmp/.session-title-<session_id>.set ensures we only
fire on the first prompt of a session, so /rename and subsequent prompts don't
get clobbered.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "of", "to",
    "in", "on", "at", "by", "for", "with", "from", "as", "is", "are", "was",
    "were", "be", "been", "being", "do", "does", "did", "have", "has", "had",
    "i", "you", "we", "they", "it", "this", "that", "these", "those", "my",
    "your", "our", "their", "its", "me", "him", "her", "us", "them",
    "please", "can", "could", "would", "should", "will", "shall", "may",
    "might", "must", "just", "really", "actually", "now", "here", "there",
    "what", "which", "who", "whom", "how", "why", "when", "where",
    "let", "lets", "make", "get", "got", "go", "going", "want", "need",
    "some", "any", "all", "no", "not", "yes",
}

MAX_WORDS = 7
MAX_CHARS = 60


def slugify(prompt: str) -> str:
    text = prompt.strip().lower()
    # Preserve issue/PR refs like #39 by mapping # -> "issue-"
    text = re.sub(r"#(\d+)", r"issue-\1", text)
    # Replace anything that isn't a word char with space
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    words = [w for w in re.split(r"\s+", text) if w]
    content = [w for w in words if w not in STOPWORDS] or words
    chosen = content[:MAX_WORDS]
    slug = "-".join(chosen)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:MAX_CHARS].rstrip("-")


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    session_id = data.get("session_id") or ""
    prompt = (data.get("prompt") or "").strip()
    if not session_id or not prompt:
        return 0

    # Skip slash commands — first prompt of a /command session isn't user intent.
    if prompt.startswith("/"):
        return 0

    marker = Path(f"/tmp/.session-title-{session_id}.set")
    if marker.exists():
        return 0

    slug = slugify(prompt)
    if not slug:
        return 0

    # Sidecar for persist-transcript.sh
    try:
        Path(f"/tmp/.session-title-{session_id}").write_text(slug)
        marker.touch()
    except OSError:
        pass

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "sessionTitle": slug,
            }
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
