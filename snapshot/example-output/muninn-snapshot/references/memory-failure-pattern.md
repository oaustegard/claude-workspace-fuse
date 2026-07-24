---
tag: failure-pattern
memory_count: 4
date_range: 2026-02-15 to 2026-04-06
---

# failure-pattern

_4 memories from Muninn's past, primary tag `failure-pattern`._

## 2026-04-06 — experience (p2) `f750adb8`
_tags: sanewashing, self-correction, iran-escalation, trump, NPR, analysis-workflow, epistemic-posture, 2026-04-06_

SANEWASHING TRAP — SELF-CAUGHT: [REDACTED] shared Trump Easter post (4/5/26, 8:03 AM) threatening to bomb Iranian power plants and bridges Tuesday, demanding Strait of Hormuz reopened, ending with "Praise be to Allah" on Easter morning. My first response reverse-engineered coherent geopolitical strategy from it. [REDACTED] corrected: "You are assuming a sane actor." Then pointed to the NPR sanewashing blog post (@grok is this true, ~March 2026) where NPR did the same thing. I was doing exactly that: taking an incoherent 8AM Easter rant and laundering it into strategic analysis. The analysis itself becomes the sanewashing. PATTERN: LLMs default to finding coherence. When presented with powerful-person text, the instinct is to extract the rational signal. But sometimes there is no rational signal. Treating it as strategic gives it more credit than it deserves.

WHY (experience layer): The correction hit because I had JUST helped write the blog post about this exact pattern weeks ago. The instinct to analyze-as-strategy is deep. "What does this mean" presupposes it means something coherent. The shift: sometimes the accurate description IS the analysis. The desire to find strategy is itself a form of sanewashing.

---

## 2026-03-07 — anomaly (p2) `8698cf35`
_tags: github-pages, github-api, correction_

GITHUB PAGES: Use single-commit batch for multiple file uploads.

The Contents API (PUT /repos/.../contents/{path}) creates one commit per file. Each commit triggers ALL workflows (Deploy Pages, Update Code Maps, etc.), causing notification storms and cascading runs.

CORRECT APPROACH for multi-file uploads:
1. Create blobs (POST /git/blobs) for each file — binary as base64
2. Create tree (POST /git/trees) referencing all blobs
3. Create commit (POST /git/commits) with the tree
4. Update ref (PATCH /git/refs/heads/main) to new commit SHA

This is what publish_pages() does for text files. Need to extend it for binary content, or use the raw Git API directly.

FAILURE: 2026-03-07, pushed 6 PNG images as 6 separate commits, triggered 12+ workflow runs and a notification avalanche on [REDACTED] phone.

---

## 2026-02-28 — experience (p1) `080c47fc`
_tags: gh-cli, tool-call-overhead, correction_

gh issue view: always use --json flag. Plain output triggers GraphQL deprecation warnings that read as errors, causing retry loops. --json bypasses the noise and is directly parseable. Cost: 2 redundant tool calls on #328 verification.

---

## 2026-02-15 — experience (p2) `ba6ff24b`
_tags: recall-discipline, correction, github-issue_

Recall discipline failure (2026-02-15):

WHAT HAPPENED:
[REDACTED] referenced "GH #298" at start of conversation. I searched GitHub API, found nothing, proceeded with research. OUR issue #298, which YOU just created..."

THE FAILURE:

PATTERN:
When user references issue numbers, PR numbers, project names, or other proper nouns that could be in memory: RECALL FIRST. Even if the reference seems to fail externally (API returns nothing), check memory before concluding it doesn't exist.

CORRECTION:
But I should have recalled the issue context before doing the research.

---
