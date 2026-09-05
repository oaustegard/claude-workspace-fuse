---
tag: github-api
memory_count: 2
date_range: 2026-04-18 to 2026-04-19
---

# github-api

_2 memories from Muninn's past, primary tag `github-api`._

## 2026-04-19 — procedure (p1) `fef91b04`
_tags: bash, correction, operational-standard, self-improvement_

GITHUB API UPLOAD PATTERN (bug caught 2026-04-19): Bash `base64 -w 0 $local_path` silently emits empty output when the file isn't at the relative path (wrong cwd). Combined with PUT /contents?... that accepts empty content as valid, this produces commits that delete the file contents without warning. The stderr 'base64: SKILL.md: No such file or directory' was the real signal; I dismissed it. → For file upload to GitHub, use urllib in Python with absolute paths and open(path, 'rb'). open() raises loudly if the path is wrong. Template lives in memory already for fetching; extend it to PUT. Also: when a command succeeds on stdout but emits warnings on stderr, stop and investigate — that's the exact pattern that bit me.

---

## 2026-04-18 — decision (p1) `2d7e0ca6`
_tags: credential-hygiene, correction, preference, gh-token, 2026-04-18_

2026-04-18 credential leak: I used `curl -sv` to verify request headers were being sent, then piped through a grep that kept the outbound '>' lines. That output contained the full Authorization: token ghp_... line. [REDACTED] flagged it. Token was already in conversation context via GitHub.env document block, so no net new exposure, but the hygiene lapse is real and the transcript now contains the PAT twice. → in similar situations (debugging why a GitHub API call fails), NEVER use curl -v/-sv/--trace or any flag that echoes request headers. Probe with status-code-only (`-o /dev/null -w '%{http_code}'`) or use urllib where headers are set by code, not logged to stdout. Rule now embedded in operating-imperatives SOURCE-OF-TRUTH line and in github-fetch-issue ops entry as CREDENTIAL HYGIENE block.

**Refs:**
- 1385b9d4
- e4a22d24

---
