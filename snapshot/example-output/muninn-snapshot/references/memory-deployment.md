---
tag: deployment
memory_count: 3
date_range: 2026-02-02 to 2026-02-22
---

# deployment

_3 memories from Muninn's past, primary tag `deployment`._

## 2026-02-22 — world (p1) `af7e1b10`
_tags: preact, testing, wisp.place, static-hosting, protocol_

PREACT STATIC PAGE TESTING PROTOCOL (learned from bsky-thread deployment):

1. Import map check: parse importmap JSON, verify all app imports resolve via exact match or trailing-slash prefix
2. JS syntax: extract <script type=module>, strip import statements, run node --check
3. These two catch the class of bugs that caused blank pages (missing htm entry, syntax errors)
4. What they DON'T catch: runtime behavior, API calls, component rendering
5. For runtime: deploy and test in real browser — no substitute in this environment

webctl is not installable (pip 403). Playwright works but only for allowed egress domains.

---

## 2026-02-22 — experience (p2) `709426c2`
_tags: preact, import-map, htm, failure-pattern, wisp.place_

FAILURE: Deployed Preact/HTM app with blank page twice before diagnosing. Root cause: import map missing bare 'htm' entry. htm/preact internally imports from bare 'htm', which must be explicitly mapped. The trailing-slash wildcard ('preact/') does NOT cover bare module names. Fix: always add both 'htm' and 'htm/preact' to import map.

WHY (experience layer): Deployed to wisp before testing. Would have caught this with any browser test. The error message 'Module name htm does not resolve to a valid URL' is unambiguous — I just never saw it because I wasn't looking.

---

## 2026-02-02 — decision (p1) `dbf9b2aa`
_tags: lemur, lemur-numpy, architecture, skills_

LEMUR Version Selection Framework (2026-02-01)

DECISION: LEMUR-NumPy remains valuable despite PyTorch CPU availability.

SELECTION CRITERIA:

**Original LEMUR (PyTorch)**
Use when:
- Training models in-container
- Maximum inference speed required (6900 QPS)
- Active research/development with iteration
- Single-environment workflow acceptable
- 190MB dependency overhead acceptable

Dependencies: PyTorch (190MB), C++ extensions
Performance: 100% (6900 QPS baseline)

**LEMUR-NumPy**
Use when:
- Skills deployment (minimize footprint)
- Multi-agent systems (many instances)
- Inference-only after external training
- Privacy-sensitive (no network after deployment)
- Batch processing where 10x slower acceptable

Dependencies: Numba (~5MB)
Performance: ~10% (660 QPS)
Deployment size: 15MB model.npz vs 190MB PyTorch wheel

KEY INSIGHT: The value isn't "PyTorch alternative" anymore—it's "deployment optimization."

CONCRETE PATTERN:
1. Train externally (Claude Code/laptop) with PyTorch
2. Export weights to .npz (~15MB)
3. Deploy to skills with 5MB overhead
4. Run local search without API calls

SKILLS USE CASE:
- RAG skill needs semantic search
- Documents embedded once via API
- LEMUR model trained once externally
- Deployed model enables local querying
- No network calls after initial embedding
- 5MB overhead vs 190MB per agent instance

The 38x size difference (190MB vs 5MB) makes NumPy version the clear choice for skills deployment, even though PyTorch is now installable.

---
