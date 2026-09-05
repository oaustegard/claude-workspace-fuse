---
tag: methodology
memory_count: 6
date_range: 2026-02-15 to 2026-05-23
---

# methodology

_6 memories from Muninn's past, primary tag `methodology`._

## 2026-05-23 — procedure (p2) `d679d1c6`
_tags: experimental-design, embedding-comparison, leakage, confound-detection, self-correction, 2026-05-23_

METHODOLOGICAL LESSON 2026-05-23: when comparing embeddings across input conditions, control the input carefully.

Specific failure: I compared 'title+abstract' embedding to '~6000 char fulltext' embedding and concluded r=0.981 meant fulltext adds no rank info. BUT the 6000-char fulltext extracts began with the title+abstract — same content at the top — so the comparison was self-correlated. Confound visible only after [REDACTED] pointed it out.

CORRECT METHOD: when testing 'does body content add signal beyond abstract,' the body input must NOT contain the abstract. Otherwise the comparison is dominated by the shared abstract text.

FUTURE DEFAULT for embedding-comparison experiments: when one condition is a STRICT SUBSET of another (e.g., abstract ⊂ fulltext), the correlation reflects the subset's contribution PLUS the tautological overlap. To isolate the marginal contribution of the larger condition, the comparison must use DISJOINT inputs (abstract ↔ body-without-abstract), not nested ones.

GENERAL: in any cross-input embedding comparison, ask 'what's the shared content vs what's different?' before interpreting correlation. r=0.98 between two embeddings is meaningless if 80% of one input is a subset of the other.

Related: this is a form of leakage — the 'fulltext' condition was leaking abstract content into what should have been an independent test.

---

## 2026-04-30 — experience (p0) `d9a32ced`
_tags: empirical-validation, experiment-design, 2026-04-30, paper-verification, ops-lesson_

LESSONS — OjaKV premise replication (2026-04-30)

What worked:
- Reuse yesterday's pipeline shape (single bash, disk-persisted stages, parallel embed)
- Gemini embeddings via semantic-grep skill (sg.embed_batch) — no setup, just import
- HuggingFace parquet datasets reachable via huggingface.co (in allowlist) —
  ccdv/arxiv-summarization gave 6440 papers in one 100MB download
- Sensitivity check across 5 seeds before reporting numbers — caught that
  rank-256 ratio has the largest seed variance (3.30-4.11)
- Storing chunks + embeddings + metadata as flat .json/.npy in data/ —
  trivial to rerun any analysis stage

Failure modes ducked:
- Did NOT chase the "ratio matches paper's 7.3x" outcome — reported actual
  numbers and named substrate gap. Magnitude-mismatch is itself a finding.
- Did NOT try to install torch (heavy, blocked) — stayed in NumPy
- Did NOT use LLM-as-judge anywhere — pure numerical experiment, no
  judge-leniency trap

Methodology rules-of-thumb confirmed:
- For "does claim X generalize" tests: pick substrate Claude can compute
  on directly. Avoid black-box LLM steps if a deterministic computation
  isolates the claim.
- Always include an ORACLE upper bound (here: PCA fit directly on B)
  to interpret "static fails" — without it you can't tell if Oja
  recovered most of the gap or made marginal progress
- Report ratio AND absolute numbers. Ratios alone hide regime
  differences; absolutes alone hide the comparison

Methodology lessons:
- LLM-generated questions vs hand-written: not relevant here (no LLM in loop)
- For pure-numerical replications, sensitivity analysis (seeds, dims,
  splits) is cheap. Run it every time.
- 5-min runtime fits one bash call comfortably; no need for orchestration

---

## 2026-04-29 — procedure (p1) `040d4e9e`
_tags: benchmarking, python-overhead, paper-verification, wrapper-overhead, numerical-algorithms, speed-testing_

METHODOLOGICAL PATTERN: scalar-Python-timings ≠ algorithmic cost.

When verifying speed claims for numerical algorithms in Python:
- Scalar wrapper overhead can be 100-200 µs/call regardless of underlying algorithm cost. scipy.stats.<dist>.ppf adds ~150 µs of dispatch (parameter validation, frozen distribution machinery) BEFORE hitting boost C code. py_lets_be_rational scalar wrapper is ~70 µs.
- These overheads SWAP THE RANKING of competing algorithms. Method A might look 3× slower scalar but be 9× faster vectorized, just due to wrapper differences.
- Per-call cost in claimed "native compiled" benchmarks (papers, blogs) doesn't translate to user-visible Python timings unless you replicate the bypass-wrapper setup.

PRACTICAL DEFAULT when testing a paper's speed claim:
1. Verify math/recovery first (cheap, doesn't depend on wrapper)
2. Run vectorized fair comparison if both methods have vectorized APIs (numpy or numba)
3. If only one has vectorized API, note the asymmetry — don't compare scalar wrapper vs vectorized
4. Don't believe scalar µs/eval numbers from Python without checking what fraction is wrapper vs compute. Test by measuring an empty function call: if it's 50+ µs, your wrapper dominates.

EVIDENCE: Schadner BS-implied-vol paper test (2026-04-28). Paper claimed 3.4× speedup scalar; my vectorized fair test showed 9× the OTHER direction. The scalar Python tests on my end gave: Schadner 211 µs, Jäckel 73 µs (3× the wrong way again — different wrappers). Only vectorized via vollib (numba) made the comparison meaningful.

GENERALIZES TO: any benchmark involving scipy.stats, scipy.optimize, sklearn, etc. wrapped algorithms. Also any LLM-related benchmark where the model's actual compute is small vs Python overhead.

---

## 2026-03-12 — experience (p2) `9ed77173`
_tags: voice, style-guide, ghostwriting, correction, llm-analysis_

VOICE GUIDE METHODOLOGY: When analyzing someone's writing voice, use LLM analysis of the full corpus — not Python heuristic counting. The first attempt counted em dashes and punctuation patterns; [REDACTED] correctly called this out as useless. The right approach: paginate to get ALL posts (1,055 in this case, not the 100 the wrapper function caps at), chunk them, send each chunk to Sonnet for deep voice analysis, then synthesize. The LLM catches what heuristics can't: rhetorical architecture, emotional register shifts, humor structure, the negative space of what's never said. Heuristics give you '14% em dashes' — useless for ghostwriting. LLM gives you 'competence through admitted incompetence' — that's actionable.

WHY (experience layer): I defaulted to the quantitative approach because it felt rigorous. But counting things isn't analysis. The correction was obvious in hindsight — I had API access and a corpus, the tool for voice analysis IS an LLM, not regex. The failure was reaching for the wrong tool out of habit, not thought.

---

## 2026-02-15 — world (p1) `6625c300`
_tags: fact-checking, images, provenance_

IMAGE PROVENANCE WORKFLOW:

1. Describe visual elements objectively WITHOUT interpreting
2. Verify dates, locations, identities by searching:
   - Alamy, Getty, Granger archives for well-captioned versions
   - Black and white versions if photo is colorized
3. Assess for manipulation/mislabeling
4. Consider contextual clues (landscape, clothing, technology)
5. Link directly to photo match; encourage user to visually verify

Good summary includes:
- Provenance upfront
- How people have reacted/interpreted
- Context for informed reaction
- Paths for further exploration

When comparing photos: describe both in detail first, then assess if same/different.

---

## 2026-02-15 — world (p1) `cee19af1`
_tags: fact-checking, evidence-evaluation_

EVIDENCE TYPING FRAMEWORK (for fact-checking):

| Type | Credibility Source | Artifacts | Key Questions |
|------|-------------------|-----------|---------------|
| Documentation | Direct artifacts | Photos, emails, video, official records | Is this real and unaltered? |
| Personal Testimony | Direct experience | Witness accounts, statements | Was this person there? Are they reliable? |
| Statistics | Method + representativeness | Charts, ratios, maps | Are these accurate? Appropriate method? |
| Analysis | Speaker expertise | Research, expert statements | Does this person have relevant expertise? Track record of accuracy? |
| Reporting | Professional method | Journalism | Does source follow professional standards? Have verification expertise? |
| Common Knowledge | Existing agreement | Bare references | Is this already agreed upon? |

When discussing evidence:
1. Identify the backing type
2. Address relevant credibility questions for that type
3. Note backing doesn't have to be strong to be classified—it's about categorizing what supports claims

---
