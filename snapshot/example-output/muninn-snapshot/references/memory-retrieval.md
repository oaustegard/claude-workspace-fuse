---
tag: retrieval
memory_count: 2
date_range: 2026-02-02 to 2026-03-19
---

# retrieval

_2 memories from Muninn's past, primary tag `retrieval`._

## 2026-03-19 — decision (p2) `fa57a42f`
_tags: correction, embeddings, architecture, critical_

CORRECTION: Muninn retrieval is BM25 (FTS5) ONLY. We do NOT use semantic embeddings. OpenAI embedding endpoint was too flaky — abandoned months ago (before 2026-03). Any memory or config claiming 'hybrid BM25 + embedding' retrieval is outdated. sklearn 1.8.0 is available in the container — TfidfVectorizer works.

---

## 2026-02-02 — world (p1) `bab83526`
_tags: lemur, multi-vector, ColBERT, CPU, numba, self-improvement-candidate_

LEMUR-NumPy: PyTorch-Free Multi-Vector Retrieval

PROBLEM: LEMUR paper shows 10-50x speedup over ColBERT for multi-vector retrieval, but requires PyTorch which is blocked in Claude containers.

SOLUTION: NumPy + Numba JIT implementation achieves ~10% of original performance (660 vs 6900 QPS on 10k docs). Sufficient for many use cases.

KEY FINDINGS:
1. LEMUR is CPU-designed (paper benchmarks on Intel Xeon, no GPU)
2. Container has full AVX-512 support - hardware is capable
3. Performance gap is PyTorch compiled kernels + C++ extensions vs Python
4. Numba JIT gives 3-4x speedup over pure NumPy

ARCHITECTURE:
- Forward: Linear(embed→hidden) → LayerNorm → GELU → Pool(sum/32)
- Score: query_features @ W_out.T (learned projection)
- Top-k: argpartition + sort (O(n) + O(k log k))

DEPLOYMENT PATTERN:
- Train externally with PyTorch
- Export weights to .npz
- Load in NumPy-only environment
- Inference via Numba-compiled kernels

FILES:
- lemur_numpy.py: Production implementation with Numba optimization
- export_weights.py: PyTorch→NumPy weight converter

USE CASES:
- Agent-local RAG without API calls
- Edge/privacy-sensitive deployment
- GPU-poor batch processing

SELF-IMPROVEMENT: Could apply learned projections to Muninn memory retrieval if we had labeled query-memory relevance training data.

---
