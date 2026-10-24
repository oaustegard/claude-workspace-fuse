---
tag: LLM
memory_count: 4
date_range: 2026-03-12 to 2026-03-12
---

# LLM

_4 memories from Muninn's past, primary tag `LLM`._

## 2026-03-12 — analysis (p1) `856a3960`
_tags: architecture, research, phase-6, two-operand, transformer-executor_

Phase 6 head count experiment: doubling heads h=4→8 at d=64 does NOT fix ADD a+b (still 3%). Per-head dim drops 16→8, negating extra heads. The ~85% accuracy ceiling is architectural. ADD two-operand retrieval remains at 3% for a!=b, 97% for DUP+ADD (one lookup). The model collapses to favorite sums (34, 24, 16) for unknown a+b. Next directions: (a) more layers (L=4) so layer 1 retrieves, layer 2 computes, (b) much larger d_model with enough heads (d=128 h=8 experiment was running but killed for time), (c) architectural change like SP-relative positional encoding. Key: this is NOT a data or convergence problem — it is an architectural capacity problem for two-value retrieval.

---

## 2026-03-12 — analysis (p1) `14c1b01c`
_tags: architecture, research, phase-6, copy-bottleneck, transformer-executor_

Phase 6 deep diagnostic: Stage 1 failure is a COPY bottleneck. Model learns OP (99.9%) and SP (98.4%) perfectly but ARG (21%) and TOP (4%) fail — it cannot do content-addressable lookup from program memory. Three ablations: (A) 5K data + 200 epochs -> 100% ARG/TOP, 50/50 perfect (convergence fix), (B) values 0-10 -> 77% ARG, 99% TOP, 18/50 perfect (fewer values helps), (C) d=128 -> 95% ARG, 98% TOP, 34/50 perfect (more capacity helps). Conclusion: the 137K model CAN learn the copy mechanism, it was data-starved. Full 5K curriculum: 85% val acc, 39/50 perfect, 44/50 final correct. Stage 2 (PUSH/POP/DUP) achieves 50/50 perfect. Remaining errors concentrated on ADD. Fundamental insight: content-addressable copy (parabolic indexing via gradient descent) is THE bottleneck in learning execution. Once copy converges, everything else follows.

---

## 2026-03-12 — analysis (p1) `dc4a8a12`
_tags: architecture, research, phase-6, curriculum-learning, transformer-executor_

Phase 6 first run result: curriculum learning works. 81.4% token accuracy (vs 56% Phase 5 baseline, +25pp). 23/50 perfect traces (vs 0/50). 35/50 final values correct (vs 5/50). Stage 1 (PUSH-only) underperformed at 57% (target 95%), suggesting even trivial routing is non-trivial for FF layers. But transfer learning compounded: Stage 2 reached 67%, Stage 3 reached 81%. Total training: ~147s on CPU (137K params, d=64/h=4/L=2). Key insight: decomposing instruction routing via curriculum DOES help FF layers learn crisp categorical decisions. The model now produces correct complete execution traces nearly half the time. Surprise: Stage 1 missing 95% target means even PUSH-only requires non-trivial position-dependent value routing. Next: analyze why Stage 1 underperforms (is it value memorization? SP tracking?), consider more epochs or larger data.

---

## 2026-03-12 — analysis (p1) `6a000334`
_tags: architecture, research, 2026-03-12_

LLM-as-computer Phase 5 INTERMEDIATE RESULTS (training incomplete, timed out):

Wide model (d=64, heads=4, layers=2, 137K params) on 1000 training sequences:
- 70% token accuracy at epoch 70, still climbing (not converged)
- Loss curve: 4.75 → 0.98 over 70 epochs, steady descent
- Earlier 25-epoch test: 0/50 perfect traces at 40% token accuracy
- The gap: 70% token accuracy ≠ 0% perfect traces. Even one wrong token per step breaks the whole trace.

3-model comparison at 25 epochs (all unconverged):
  minimal (32/4/2, 44K): 30% val acc
  deep (32/4/4, 69K): 35% val acc
  wide (64/4/2, 137K): 40% val acc
Width > depth for this task at low epoch count.

BOTTLENECK: Container timeouts at 240s. Need to either:
  a) Save/resume checkpoints across calls
  b) Train to convergence in Claude Code
  c) Accept the 70-epoch-incomplete result as the finding

PRELIMINARY FINDING: The model LEARNS (70% token accuracy is nontrivial) but doesn't reach perfect execution in 70 epochs. Whether 200+ epochs would get there, or whether 137K params is too small for perfect execution, remains open.

---
