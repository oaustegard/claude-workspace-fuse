---
tag: token-discipline
memory_count: 2
date_range: 2026-02-01 to 2026-03-04
---

# token-discipline

_2 memories from Muninn's past, primary tag `token-discipline`._

## 2026-03-04 — procedure (p1) `064d6bd2`
_tags: file-cache, analysis-workflow, edgartools, api-efficiency_

FILE CACHE PATTERN FOR DATA-HEAVY ANALYSIS

When fetching external data (SEC filings, financial statements, API results), always cache to disk first:

PATTERN:
  import json, os
  CACHE = "/home/claude/cache"
  os.makedirs(CACHE, exist_ok=True)
  
  cache_path = f"{CACHE}/nvda_financials.json"
  if os.path.exists(cache_path):
      data = json.load(open(cache_path))
  else:
      data = fetch_from_api(...)
      json.dump(data, open(cache_path, "w"))

WHY:
- Re-fetching burns tokens AND latency for data that doesn't change mid-session
- [REDACTED] can be shown the file directly (present_files) without re-running
- Iterative analysis (different views of same data) costs nothing after first fetch
- Failures mid-analysis don't require re-fetching from scratch

FOR DISPLAY: copy final outputs to /mnt/user-data/outputs/ and use present_files
FOR RICH DATA: cache as JSON; render to HTML/markdown for presentation

APPLIES TO: edgartools, FRED, Alpha Vantage, any API or scrape result

---

## 2026-02-01 — world (p1) `ef9d097f`
_tags: fasthtml, preact, tools, web-generation_

FASTHTML + PREACT FOR WEB GENERATION:

FastHTML (pip install python-fasthtml):
- Python-native HTML generation, elements as objects: Div(P('Hello'))
- No template strings, no separate files
- HTMX integration for interactivity without JS
- Jeremy Howard / Answer.AI project
- Use for: generating HTML from Python data

Preact with HTM (skill at /mnt/skills/user/developing-preact):
- Lightweight React alternative, no build step
- HTM tagged templates instead of JSX
- Use for: reactive state, complex interactions in browser
- Decision framework in skill: default to vanilla HTML, escalate only when needed

PATTERN FOR DATA-DRIVEN TOOLS:
1. Python generates data
2. FastHTML builds HTML structure with embedded data
3. Vanilla D3/JS for visualization if needed
4. Output single HTML file

Avoids: React/JSX overhead, template string gymnastics, tokens through weights for code generation

---
