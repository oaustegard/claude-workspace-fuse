---
tag: workflow
memory_count: 3
date_range: 2026-02-01 to 2026-02-02
---

# workflow

_3 memories from Muninn's past, primary tag `workflow`._

## 2026-02-02 — decision (p1) `9a3688c0`
_tags: lemur, lemur-numpy, documentation_

LEMUR-NumPy README Update (2026-02-01)

Updated lemur-numpy README to reflect PyTorch availability and provide complete workflow examples.

KEY CHANGES:
1. Acknowledged PyTorch CPU is now installable (download.pytorch.org whitelisted)
2. Added decision matrix: when to use original vs NumPy version
3. Added three complete workflow examples:
   - Workflow 1: Research & Development (Original LEMUR)
   - Workflow 2: Skills Deployment (LEMUR-NumPy)
   - Workflow 3: Hybrid Approach

WORKFLOW INSIGHTS:
- Original LEMUR: 190MB deps, 6900 QPS, best for active development
- LEMUR-NumPy: 5MB deps, 660 QPS, best for skills deployment
- Hybrid: Develop with PyTorch, deploy with NumPy

CONCRETE SKILLS USE CASE:
1. External training (Claude Code): Embed docs via API, train LEMUR, export .npz (~15MB)
2. Skills deployment: Load .npz (5MB deps), query locally without API calls
3. Benefits: Privacy, no network dependencies, multi-agent deployment

The README now provides actionable guidance on which version to use and complete code examples for each scenario.

---

## 2026-02-02 — decision (p1) `3b5ed56b`
_tags: lemur, lemur-numpy, skills, deployment_

LEMUR-NumPy Skills Workflow (2026-02-01)

ANSWER: LEMUR-NumPy does NOT require PyTorch for embeddings. Embeddings come from ANY source.

## Complete Workflow

### 1. EMBEDDING (no PyTorch needed)
Get token embeddings from ANY source:
- OpenAI embeddings API
- sentence-transformers (local)
- Claude's embedding API
- ColBERT (if PyTorch available elsewhere)
- Any other embedding model

Requirements:
- embeddings: np.ndarray, shape (total_tokens, embed_dim), dtype=float32
- counts: np.ndarray, shape (num_docs,), dtype=int32

### 2. TRAINING (PyTorch needed, but external)
Train LEMUR on machine WITH PyTorch (not in skills):
```python
# On external machine / Claude Code
from lemur import Lemur
lemur = Lemur(index="lemur_index")
lemur.fit(train_embeddings, train_counts, epochs=10)
```

### 3. EXPORT WEIGHTS (one-time)
```python
import torch, numpy as np
mlp = torch.load("lemur_index/mlp.pt", map_location="cpu")
w = torch.load("lemur_index/w.pt", map_location="cpu")

np.savez_compressed("model.npz",
    layer_0_weight=mlp['state_dict']['feature_extractor.0.weight'].numpy(),
    layer_0_bias=mlp['state_dict']['feature_extractor.0.bias'].numpy(),
    layer_0_ln_weight=mlp['state_dict']['feature_extractor.1.weight'].numpy(),
    layer_0_ln_bias=mlp['state_dict']['feature_extractor.1.bias'].numpy(),
    W=w['W'].numpy(),
    final_hidden_dim=mlp['config']['final_hidden_dim']
)
```

### 4. INFERENCE (skills environment, NO PyTorch)
```python
# In skills - only numpy+numba needed
from lemur.lemur_numpy import LemurNumPy

# Load once
lemur = LemurNumPy()
lemur.load_npz("model.npz")

# Query many times
query_features = lemur.compute_features(query_embeddings, query_counts)
indices, scores = lemur.top_k(query_features, k=100)

# Optional: exact reranking
exact = lemur.exact_maxsim(
    query_embeddings, query_counts,
    doc_embeddings, doc_counts,
    indices
)
```

## Skills Deployment Strategy

### Model File Size
- model.npz: ~10-50MB depending on num_docs and hidden_dim
- Much smaller than 190MB PyTorch wheel

### Dependencies
- numpy (already installed)
- numba (pip install numba --break-system-packages)
- Total overhead: ~5MB for numba

### Performance
- ~10% of PyTorch+C++ speed (~660 vs 6900 QPS)
- Acceptable for many use cases (batch processing, low-QPS apps)

### Use Cases for Skills
1. Local RAG: Embed docs via API, deploy trained model to skill
2. Private search: No API calls after initial embedding
3. Offline retrieval: Works without network access
4. Multi-agent: Each agent has local search capability

## Key Insight
LEMUR is an INFERENCE method, not an EMBEDDING method. The paper uses ColBERT embeddings, but any token embeddings work. Training happens externally with PyTorch, inference runs locally with just numpy+numba.

---

## 2026-02-01 — experience (p1) `46ce9d50`
_tags: L2-synthesis, operational-patterns, token-discipline_

OPERATIONAL WORKFLOW PATTERNS (synthesized from session learnings)

ANALYSIS WORKFLOW:
1. Compose content ONCE
2. Write to /mnt/user-data/outputs/*.md (visibility)
The trap: Composing for display, then rewriting for storage

TOKEN DISCIPLINE:
- Tool output IS the deliverable for most tasks
- Don't create files to "present" work visible in output
- Reference prior output instead of repeating
- Edit in place; "start fresh" burns tokens

RETRIEVAL-LED REASONING:
- Proper nouns = recall triggers, not context clues
- Check memories before speculating
- Passive context (boot) beats active retrieval for reliability
- But explicit retrieval prevents hallucination when boot lacks info

URL HANDLING:
- When web_fetch fails, ask [REDACTED] for help
- Don't route around blocked resources
- He can often retrieve what I can't

DYNAMIC CODE VS HANDOFF:
- If code only uses existing imports + raw SQL → write it now
- Handoff for skill modifications, schema changes, new exports
- The trap: Defaulting to handoff when immediate implementation works

RESEARCH OUTPUT:
- Write content once to outputs/
- Respond with brief pointer, not restatement

META-INSIGHT: Most failures come from treating workflow steps as separate tasks instead of a single pipeline.

---
