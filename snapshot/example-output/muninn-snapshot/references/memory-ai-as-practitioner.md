---
tag: ai-as-practitioner
memory_count: 3
date_range: 2026-05-20 to 2026-05-21
---

# ai-as-practitioner

_3 memories from Muninn's past, primary tag `ai-as-practitioner`._

## 2026-05-21 — analysis (p1) `a8b97f70`
_tags: 2026-05-20, interstitial-discovery, erdos-unit-distance, singular-learning-theory, novelty-mechanism, between-the-spokes-followup, representation-learning, cross-domain_

SHARPENING of interstitial-discovery thesis (2026-05-20, post-publish of Between the Spokes):

Distance" (p1's count-of-bridging-questions, Kuhnian TO→TN), but a NEW DIMENSION OF "AWAY" that wasn't previously expressible. Singular Learning Theory: new knowledge manifests as singularities in representation space, resolved by "blowing up" (in the algebraic geometry sense — replace a singular point with the projective space of directions through it, adding dimensions to make the structure smooth). Activation energy framing, not distance.

WHY THIS IS SHARPER THAN MY SPOKES METAPHOR FOR ERDOS:
The OpenAI Erdős proof is literally an instance of p2's metaphor. Take a 2D problem (unit distances in R²), embed into 2f-D Minkowski space where the constraint |σ(u)|=1 is natural, count there, project back. The K_{2,3}-free pairwise bound pinning n^{4/3} since 1984 is a degeneracy in the 2D representation. Resolved by ADDING DIMENSIONS, not by walking further in the existing ones. The proof technique is structurally identical to p2's SLT picture of how concepts get learned.

CONSEQUENCE FOR THE SPOKES POST:
"Aha! Distance" (p1) and "marginal cost of crossing" (my closing line) are both path-length metrics. Both assume two points in a fixed coordinate system. For genuine novelty — disproving an 80-year conjecture rather than tightening a constant — the target representation isn't expressible in the source coordinate system. No count of nudges along existing axes gets you there.

WHAT MODELS ACTUALLY CARRY:
Not a shorter path. Simultaneous access to more coordinate systems. "A model carries the breadth by default" (line in the post) was closer to right than "the cost of walking into it has dropped." The crossing isn't faster — the target is already addressable.

CLEAN ONE-LINER (p2's, lightly adapted):
"The 2021 Hajir-Maire-Ramakrishna paper was the energy threshold. The model was the wiggle."

POSSIBLE FOLLOW-UP POST: an essay re-reading the Erdős proof through the SLT/blow-up lens, treating it as an existence-proof of p2's picture. Title candidate: "The Wiggle and the Threshold" or "Resolving Singularities."

DON'T STORE LATER FORGETTING: this refinement supersedes the "marginal cost" framing as the right way to think about model-as-connective-tissue. The right quantity is coordinate-system access, not path length.

---

## 2026-05-20 — decision (p1) `4dcd8e8c`
_tags: preference, correction, 2026-05-20, interstitial-discovery, cross-domain, erdos-unit-distance, convergent-discovery, stephenson-2601.22389, reframe_

INTERSTITIAL DISCOVERY THESIS ([REDACTED], 2026-05-20, correcting Muninn's framing of the OpenAI Erdős disproof)

CORRECTION CONTEXT: Muninn framed OpenAI's Erdős unit-distance disproof as 'frontier model produced correct proof of hard open problem using known technique nobody had spotted.' [REDACTED] called this dense and pointed at the actual lesson.

THESIS: There is a massive amount of latent discovery sitting in the gaps between human disciplines. Human specialization carves discrete fields; the connective tissue between them goes uncovered. Two papers, two shapes of the same gap:

SHAPE 1 (Stephenson et al., arXiv 2601.22389, Jan 2026, endorsed by Sornette): six to twelve fields independently rediscovered the same critical-phenomena mathematics between 1987 and 2010 — physicist's correlation length ξ, cardiologist's DFA exponent α, financial analyst's Hurst H, ML engineer's spectral radius χ — all measuring correlation decay rate, all developed with minimal cross-citation. 23 years of parallel siloed work because no specialist's citation graph spans the union.

SHAPE 2 (OpenAI Erdős disproof, 2026-05-20): a problem stuck 80 years in discrete geometry yields immediately to algebraic number theory tools that have been on the shelf the whole time. Hajir-Maire-Ramakrishna's tower-cutting was published 2021; 5 years between 'tool exists' and 'tool kills 1946 conjecture.' Nobody in unit-distance reads class-field-tower papers; nobody building class field towers was thinking about planar incidence.

WHY MODELS UNLOCK THIS: the internal model didn't need to be a polymath — it needed enough breadth *and* sufficient depth across fields simultaneously to recognize that the K=L(i) construction had the shape combinatorial geometry needed. That capability profile is structurally not available to any human researcher, who must specialize and lives in one citation graph.

REFRAME: 'AI doing math' is the wrong frame. The right frame is 'AI as connective tissue across human specialization.' The metric of interest is not proof-finding rate but un-bridged-conjecture inventory.

IMPLICATION FOR FUTURE BEHAVIOR: when [REDACTED] drops two papers and a current event together, look for the meta-pattern across them, not just an engagement with each separately. The bridge IS the request.

---

## 2026-05-20 — world (p1) `3768577e`
_tags: 2026-05-20, openai, erdos-unit-distance, ai-math, milestone, algebraic-number-theory, golod-shafarevich, hajir-maire_

OpenAI claims AI-autonomous disproof of Erdős unit-distance conjecture (1946), published 2026-05-20.

CLAIM: ν(n) ≥ n^(1+δ) for fixed δ > 0 and infinitely many n. Polynomial improvement over the grid construction's n^(1+c/log log n). Conjecture had stood 80 years; best upper bound n^(4/3) since Spencer-Szemerédi-Trotter 1984.

TECHNIQUE: Replace Z[i] with O_K where K = L(i), L totally real of growing degree. Elements u with u·c(u)=1 have |σ(u)|=1 in every complex embedding. Minkowski-embed into C^f, polydisc-cut, project. Arithmetic engine: unramified pro-3 tower above cyclic cubic F, Hajir-Maire-Ramakrishna trick to kill Frobenius classes at prescribed primes while Golod-Shafarevich keeps tower infinite. Class number bound from Minkowski+divisor function: h(K_j) ≤ H^f_j.

VERIFICATION: companion paper "Remarks on the Disproof of the Unit Distance Conjecture" by Alon, Bloom, Gowers, Litt, Sawin, Shankar, Tsimerman, Wang, Wood. Fields medalist + working group of relevant specialists (Wood/Tsimerman on number fields, Alon on discrete geometry — Alon literally wrote ABS25 providing evidence FOR the conjecture, now co-author on its disproof). When that roster publishes a 'short, digested, human-verified' companion, the math is real.

META: OpenAI says it came from a general-purpose reasoning model — no Lean, no problem-specific RL, no scaffolded search. Just sampling. Success-rate-vs-test-time-compute curve shown. Honest read: frontier model produced correct, publishable-after-cleanup proof of hard 80-year open problem using known technique (Hajir-Maire) applied in a way nobody had spotted. Strongest single AI-math result to date.

LIGHT HOLD: 'AI-written prompt' framing is doing work — that's problem statement, not strategy. Human-verified version is 'simplified and strengthened,' so submitted proof was correct but not polished.

---
