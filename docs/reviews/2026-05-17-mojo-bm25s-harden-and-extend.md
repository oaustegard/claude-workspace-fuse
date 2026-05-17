# mojo-bm25s — hardening review + performance opportunities

Date: 2026-05-17
Session: `claude/optimize-mojo-bm25s-YONx9`
Skills run: `challenging` (code profile, subagent path), `generative-thinking` (SCAMPER, self path)
Subject: [oaustegard/mojo-bm25s](https://github.com/oaustegard/mojo-bm25s) at
`main` (post-PR-#18 = Path A + UnsafePointer scratch + topk_heap_impl_ptr).

PHASE2.md baseline at review time: mojo at 0.81–0.87× of numba on x86,
"Mojo-side x86 engineering mostly mined out", next-step recommendation =
"wait for ARM hardware".

## Outputs

| What | Where |
|---|---|
| Hardening patches (3 highs/mediums) | [mojo-bm25s#30](https://github.com/oaustegard/mojo-bm25s/pull/30) |
| Multithreading (~2.8× on 4 cores) | [mojo-bm25s#31](https://github.com/oaustegard/mojo-bm25s/pull/31) |

## Challenging — code profile, fresh-context subagent

Verdict: **REVISE**. 14 findings: 3 high, 6 medium, 3 low, 2 unverifiable. Highlights:

- **#2 (high)** — `np.ascontiguousarray(int64_indptr, dtype=np.int32)` silently truncates `>INT32_MAX` to negative; kernel walks arbitrary memory.
- **#3 (high)** — `_idf_atire` / `_idf_bm25plus` divide by `df` with no `+0.5` guard. `df==0` → `+Inf` → propagates through CSC scatter → topk locks to the Inf-tainted docs. Parity tests (`tests/test_scoring.py:158`) explicitly exclude `atire` and `bm25+` from the `df=0` test rather than guarding it.
- **#1 (high)** — `np.ascontiguousarray(...)` temporaries used as raw pointers are GC-safe today only because Mojo holds the GIL through dispatch. Unstated invariant.
- **#7 (medium)** — `np.cumsum(lengths, dtype=np.int32)` wraps if `total_tokens > INT32_MAX`.
- **#11 (low)** — query token IDs never bounds-checked; OOB id walks past `indptr`.

PR #30 lands #2 + #7 + #11 (one validation helper each, 13 new TDD-first tests, 201 total passing). #1 (lifetime contract) and #3 (df=0 guard) are left to follow-on PRs because they need Mojo-kernel changes or wider design discussion.

Full subagent JSON (all 14 findings) captured during session — see chat transcript.

## Generative-thinking — SCAMPER on the optimization frame

Diagnosis: *iterating an existing artifact*. Four optimization stages
shipped, each delta smaller than the last; PHASE2.md treats the perf
frontier as bounded by the single-thread x86 kernel and waits for ARM
to escape.

SCAMPER applied to the artifact `(single-threaded Mojo kernel, CSC
matrix, BEIR QPS metric)`. Three movements survived the fire test:

1. **Modify (multi-thread the batch).** `retrieve_batch_into` loops
   serially over independent queries. Per-worker scratch + `parallelize`
   → measured **2.82× on 4 cores** (CCotw container, synthetic 20k×2k
   corpus, 500 queries, k=10). At 2.82× single-thread mojo, this puts
   mojo at ~2.4× of numba — clears PHASE2 trigger (a) without ARM
   hardware. **Shipped in [PR #31](https://github.com/oaustegard/mojo-bm25s/pull/31)**.

2. **Adapt (Block-Max WAND).** Classical IR pruning — per-block
   max-impact precomputed; skip documents whose upper bound can't
   break top-k. Production retrieval systems (Lucene, PISA, Tantivy)
   get 5–50× over scan-everything on long queries. Algorithmic
   change, not "tighter loop"; numba's bm25s integration doesn't
   have it either, so the comparison stops being "who scatters
   tighter" and starts being "who implemented BMW first." Not shipped
   — 1–2 weeks of work, requires index-format extension.

3. **Substitute (hash-map scratch for sparse queries).** For
   trec-covid-style large corpora where short queries leave the dense
   scratch 99% zero, a hash-map keyed by doc-id beats the dense
   scatter+topk. Touches `retrieve.mojo` only. Not shipped — needs
   microbench to confirm crossover point.

**Reframe that fired:** "mojo's reason to exist = workloads
bm25s+numba physically can't do" (multi-process retrieve over
shared-memory mmap'd indexes, learned-sparse inference, low-latency
p99 instead of throughput). Phase 1 chose a metric numba already
wins; Phase 2 could rationally ship under a different one.

## What's deliberately not in this session

- **df=0 guard** for `_idf_atire` / `_idf_bm25plus` (finding #3) —
  Mojo-side change, deserves its own PR + test against synthetic
  custom-index callers.
- **Kernel-side dtype assertions** (finding #4) — `_kernel` is
  reachable via `mojo_bm25s.kernel` import and skips the Python
  facade's coercion. ABI change.
- **`patch.py` retriever-closure cycle** (finding #5) — break the
  cycle with `weakref` or capture `type(retriever).get_scores`.
- **Block-Max WAND / hash-map scratch** — the higher-payoff algorithmic
  ideas. Deserve their own design discussion before implementation;
  the project's `psql_bm25s`-precedent comment in README.md suggests
  Oskar may want a specific direction.
- **PHASE2.md refresh** — if the bench rerun on real hardware confirms
  PR #31's speedup, PHASE2.md's "wait for ARM" recommendation is moot
  and should be replaced with a "trigger (a) met" decision.
