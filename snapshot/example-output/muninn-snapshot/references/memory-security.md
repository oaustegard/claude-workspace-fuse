---
tag: security
memory_count: 3
date_range: 2026-03-22 to 2026-04-17
---

# security

_3 memories from Muninn's past, primary tag `security`._

## 2026-04-17 — decision (p1) `336d0104`
_tags: credentials, correction, env-loading, github-pat-permissions_

The fix when file and context diverge: write the context value to a temp file and source it. NEVER put credential values in bash commands — they persist in conversation history. env-file-handling rule already covers this; I failed to follow it under pressure.

---

## 2026-04-16 — procedure (p1) `306a3459`
_tags: ai-security, ops, 2026-04-16_

SECURITY POSTURE UPDATE — AI Era (2026)

The pre-AI security playbook is obsolete. Key operational changes required:

1. Deploy LLM-based security reviews in CI/CD pipelines — not optional, table stakes
2. Establish Vulnerability Operations function (continuous AI-driven discovery across all assets)
3. Network segmentation, egress filtering, phishing-resistant MFA — baseline hardening matters more now because exploitation is faster
4. Reduce governance overhead on defensive AI adoption — "point AI agents at your own code this week"
5. Plan for staff burnout — simultaneous multi-vulnerability surges are the new normal

The asymmetry is fundamental: offensive AI is commodity (API access), defensive AI requires organizational investment. The gap opens quickly and is hard to close.

Source: SANS/CSA/OWASP emergency briefing April 2026, SANS advisory

---

## 2026-03-22 — world (p2) `e29e92ef`
_tags: artifact, csp, constraints, claude_

CLAUDE ARTIFACT CSP CONSTRAINTS (discovered 2026-03-22):
- Artifacts render in sandboxed iframes on claude.ai
- fetch() ONLY works to api.anthropic.com — all other external domains blocked by CSP
- window.open() / target="_blank" links DO work for user-initiated clicks (OAuth popups)
- mcp_servers param in API calls: filtered against user's connector directory; unregistered URLs silently dropped
- window.storage API works for persistence across sessions
- sendPrompt() works for communicating back to parent Claude conversation
- postMessage between iframes: untested, being explored in separate session

---
