# woodall/ — τ=3 counterexample search for Woodall's conjecture

Machinery for [claude-workspace#163](https://github.com/oaustegard/claude-workspace/issues/163):
a CEGAR SAT/CP-SAT verifier for dijoin packing, calibrated against every known
Edmonds–Giles counterexample, plus generators that hunt for an uncapacitated
digraph with every dicut of size ≥ 3 but no 3 pairwise disjoint dijoins.

**Status: no ν<τ candidate found.** All calibration gates pass; all search
families so far produce packings (conjecture-consistent). See "Run log" below.

## Layout

| file | contents |
|---|---|
| `digraph.py` | bitmask digraph: closed-set/ideal enumeration, τ, dicuts, dijoin test (reversal + strong connectivity), violated-dicut extraction, SCC condensation, cheap iso-invariant key |
| `pack.py` | CEGAR packing loop; backends: OR-tools CP-SAT and python-sat CaDiCaL; `solve_full()` = one-shot vs *all* dicuts (independent formulation); `cross_verify_candidate()` runs every path |
| `brute.py` | backtracking exact ν for tiny instances (independent of SAT stack) |
| `examples.py` | (D₁,u₁) Schrijver 1980, ring(i) generalization, (D₂,u₂)/(D₃,u₃) Cornuéjols–Guenin 2002, D₂′ = D₂−(14→8) (Williams) |
| `generator.py` | null-arc gadget liftings (drop/keep/subdivide×1/×2/contract), structure-guided random DAGs, hard filters |
| `exhaustive.py` | exhaustive scan of ALL simple DAGs up to n vertices (topological-labeling enumeration; no iso-dedup, so nothing can be silently dropped) |
| `search.py` | search driver, JSONL logging, candidate cross-verification |
| `tests/` | the calibration gates |
| `runs/` | JSONL run logs |

## Repro commands

```bash
pip install ortools python-sat pytest

# calibration gates (must all pass before trusting any search output)
python3 -m pytest woodall/tests/ -v

# search families
python3 -m woodall.search liftings --base D1 --limit 25000
python3 -m woodall.search liftings --base D1 --gadgets drop,keep   # exhaustive (2^12)
python3 -m woodall.search liftings --base D2 --limit 25000
python3 -m woodall.search liftings --base D3 --limit 25000
python3 -m woodall.search random --n 12 --count 25000 --seed 163

# exhaustive scan of ALL simple DAGs with <= 8 vertices
python3 -m woodall.exhaustive 8
```

## Verifier design

- **τ**: enumerate closed vertex sets (no entering arc) by walking a topo
  order — a vertex may join S only when all in-neighbours are in S; τ = min
  capacity over induced dicuts. Exact for the sizes searched (n ≲ 20).
- **ν ≥ k (CEGAR)**: working dicut set C starts from principal dicuts
  (ancestor closures / descendant-complements per vertex). SAT model: active
  arc × color booleans, at-most-one color per arc, every dicut in C hit by
  every color. On SAT, each color class is checked for *real* dijoin-ness by
  the reversal characterisation (J is a dijoin ⟺ D + J⁻¹ strongly
  connected); failing classes contribute violated dicuts (source components
  and complement-of-sink components of the condensation of D + J⁻¹) and the
  loop repeats. On UNSAT, no k-packing exists; the final C is the
  certificate.
- **Cross-verification of any UNSAT hit**: CEGAR × {CP-SAT, CaDiCaL} plus
  one-shot full-dicut-enumeration × both backends, plus (tiny cases) the
  `brute.py` backtracker. A DRAT-emitting run (kissat/cadical CLI) is left
  as follow-up wiring; nothing has needed it yet — no UNSAT candidate has
  survived filters to date.

## Calibration gates (all green)

1. **Fact 7.1** — (D₁,u₁): ν=1, τ=2 ✓. The four special joins of survey §7.1
   ({a,c,d,f,h}, {d,f,g,i,b}, {g,i,a,c,e}, {b,h,e}) are each verified
   dijoins, each active arc in exactly two ✓. D₁ ≅ ring(3) ✓.
2. **Facts 8.1/8.2** — (D₂,u₂), (D₃,u₃): ν=1, τ=2 ✓; D₂′ (Williams) also
   ν=1, τ=2 ✓. D₃'s arc set is invariant under (TM M2)(TL R2)(TR L2)(ML MR),
   used as a transcription anchor ✓.
3. **Rings** — i=5,7 are counterexamples; i=4,6 are not ✓.
4. **Brute-force agreement** — 100+ random small DAGs (n≤8): CEGAR/CP-SAT,
   CEGAR/CaDiCaL and the backtracker agree on ν, and ν=τ on all of them ✓.
5. Reversal characterisation of dijoins checked against the definitional
   "meets every dicut" test on 100+ (digraph, arc-set) pairs ✓.

Transcription provenance: all three counterexamples were reconstructed from
the figures of Feofiloff's survey (`ime.usp.br/~pf/dijoins/woodall/survey1-en.pdf`,
Figures 6, 9, 10 read at 300–400 dpi), not from a remembered arc list, per
the issue's calibration instructions. The calibration suite is the arbiter:
**do not edit an arc list in `examples.py` without re-running the gates.**

## Hard filters (proven-good classes, excluded from search)

1. DAGs only (WLOG; `contract_sccs()` applied after gadget liftings).
2. Source-sink-connected DAGs are good (Schrijver 1982; Feofiloff–Younger
   1987) — generator discards them.
3. Single-source or single-sink DAGs are good — discarded.
4. τ ≥ 3 required (computed exactly; τ ≤ 2 is safe by Frank's k=2 proof).

Additional guidance from Schrijver's discussion notes
(`homepages.cwi.nl/~lex/files/woodall.pdf`), *Observations on Woodall's
conjecture*: a minimal counterexample may be assumed **reduced** — acyclic,
weakly 3-arc-connected, every size-k dicut determined by a single source or
sink, all internal vertices of degree 3. Encoded as heuristics for the random
family (they are theorems only for minimal counterexamples).

## Literature gate (checked 2026-07-23)

Sources examined for prior computational coverage of the τ=3 space:

- Feofiloff survey + `ime.usp.br/~pf/dijoins/` hub — theory + the
  counterexample catalog only; no machine search reported.
- Egres Open ("Woodall's conjecture") — status page; partial results
  (Schrijver/FY source-sink-connected; Lee–Wakabayashi series-parallel;
  Mészáros prime-power partition-connectivity); no computational ranges.
- Open Problem Garden — statement only.
- Schrijver, *Observations on Woodall's conjecture* (CWI notes) — structural
  reductions for minimal counterexamples; no computation.
- Chudnovsky–Edwards–Kim–Scott–Seymour, *Disjoint dijoins* (JCTB 2016) —
  proves packing results for classes of dicuts; notes all known EG
  counterexamples have active part = three disjoint paths; no search.
- Abdi–Cornuéjols–Zlatin line (arXiv:2310.19472, SIDMA 2023–24; dyadic
  packing 2024) — theoretical decompositions (dijoin + (τ−1)-dijoin); even
  k=2 "two disjoint dijoins when τ≥2... into dijoin+2-dijoin" refinements;
  no exhaustive small-case computation published.
- Hwang, *The Edmonds–Giles Conjecture and its Relaxations* (UWaterloo 2022)
  — relaxations; no computational verification.
- Williams, *Packing directed joins* (UWaterloo MSc 2004): **not obtained**
  (no digital copy located; UWSpace hosts other theses only). His derived
  counterexample catalog is represented here only via D₂′ from the survey's
  description. Follow-up: request via library loan and encode the full
  catalog.

**Conclusion: no published exhaustive computational verification of
Woodall's conjecture for τ=3 was found — the small-instance space appears
unmined.** (Strongest known theory constraining a counterexample: it must
fail source-sink-connectivity, fail series-parallelness, have τ ≥ 3, and by
Mészáros' theorem k=3 = prime power means its underlying graph must not be
(6,12)-partition-connected... — see Egres page.)

## Run log / negative results

See `runs/*.jsonl` for raw logs. Headline findings (no ν<τ candidate
anywhere):

- **Every simple DAG on ≤ 7 vertices satisfies Woodall for τ ≥ 3 —
  exhaustively.** `exhaustive.py` scanned all 2 097 152 upper-triangular
  adjacency codes at n=7 (plus everything smaller): *zero* DAGs combine
  "every source out-degree ≥ 3, every sink in-degree ≥ 3" with failure of
  source-sink-connectivity. The candidate space at n ≤ 7 is literally empty
  — any τ=3 counterexample among simple digraphs (WLOG a simple DAG) needs
  **≥ 8 vertices**. Scope note: contracting SCCs of a general digraph can
  create parallel arcs, and subdivision does not obviously preserve
  counterexample-hood, so multigraph DAGs are *not* covered by this claim.
- **Exhaustive {drop, keep} resolutions of all three EG counterexamples
  fail.** All 2¹² = 4096 resolutions of D₁ and all 2¹⁴ = 16384 resolutions
  each of D₂ and D₃: every lifting reaching τ ≥ 3 (24 / 100 / 18 of them
  respectively, after iso-dedup) packs 3 disjoint dijoins. Likewise
  exhaustive D₁ × {drop, contract} (1 survivor, packs) and D₁ × {keep, sub1}
  (1376 survivors, all pack). The null arcs cannot be locally resolved by
  deletion/promotion alone — new small dicuts (τ ≤ 2) or restored
  source→sink reachability kill the conflict structure every time. This is
  the quantitative form of "the known-open lifting question" from the issue.
- **Sampled 5-gadget liftings** (drop/keep/sub1/sub2/contract, 25 000 per
  base): every filter survivor packs — D₁: 4370/4370, D₂: 5400/5400, D₃:
  4335/4335. Dominant kill reasons: τ ≤ 2 (new small dicuts from `drop`,
  ~50% of instances) and restored source-sink-connectivity (`keep`/`sub*`,
  ~10%).
- **Structure-guided random DAGs**: n=12: 134/134 pack, n=14: 213/213,
  n=16: 196/196. No ν < τ candidate anywhere (14 648 τ≥3 instances tested
  in the sampled sweep, 0 UNSAT).
