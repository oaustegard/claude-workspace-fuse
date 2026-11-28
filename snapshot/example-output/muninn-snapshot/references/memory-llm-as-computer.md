---
tag: llm-as-computer
memory_count: 12
date_range: 2026-03-12 to 2026-04-24
---

# llm-as-computer

_12 memories from Muninn's past, primary tag `llm-as-computer`._

## 2026-04-24 — decision (p1) `a5353091`
_tags: issue-95, issue-100, pr-101, poly-compiler, property-testing, compiler-bug, copy_var, test-authorship, 2026-04-23_

llm-as-computer #95 (X3b property tests): opened PR #101, filed companion bug #100. Added TestRoundTripProperty (N=100 seeded random polys, 1-4 vars, deg 1-3, coeffs [-5,5], contiguous vars from 0, no constant term), TestEdgeCases, TestGeneratorReproducibility. Result: 60/100 random seeds + 3 edge cases fail — exposed real bug in poly_compiler._CompilerContext.copy_var: depth>2 ROT/SWAP loop never surfaces the target variable. x0+x1+x2+x3 (one of #95's own edge cases) compiles to 3*x2+x3. n_vars<=2 works; n_vars>=3 breaks. PR left without xfail markers — failing tests are the point, block merging until compiler fixed. Existing #94 tests (114) still pass; #94 passed only because every hand-picked case was <=2 vars. Pattern: property testing found a bug class unit testing missed.

---

## 2026-03-25 — procedure (p1) `c0dd2b13`
_tags: executor, step-limit, issue-52_

Fixed llm-as-computer executor step limits: default raised from 50K to 5M in both executor.mojo and runner.py. Added --max-steps N CLI flag to Mojo binary. runner.py now passes max_steps through and scales subprocess timeout. Changes are ephemeral (in /mnt/skills/user/), need to be committed to repo via issue or PR. Issue #52 tracks the benchmarking work.

---

## 2026-03-25 — world (p0) `853f5c06`
_tags: benchmark, mojo, percepta, issue-52, 2026-03-24_

LLM-as-computer #52 benchmark results (2026-03-25): Mojo executor 67-126M steps/sec, Python fallback 2.1-3.1M steps/sec. Both O(1)/step at all scales (10K, 100K, 1M). 1.2M steps in 17ms Mojo, 561ms Python. Memory ~65 bytes/step in Python (65MB at 1M). Speedup 28-44x constant across scales — both use dict-based lookup, not attention scan. Hull-accelerated attention path (NumPy/TorchExecutor) NOT yet benchmarked at scale. Remaining: torch comparisons, bubble sort/primes (need locals/memory opcodes), Mojo memory profiling.

---

## 2026-03-24 — world (p1) `c98f5c0b`
_tags: shorthand, lac, container_

SHORTHAND: 'lac' = 'llm-as-computer' — refers to the containerized compute environment (the Linux container Claude operates in during conversations). Usage: 'redo X against lac' means 'adapt X for the container environment'.

---

## 2026-03-24 — decision (p1) `50639a78`
_tags: decision, architecture, issue-28, restructure_

llm-as-computer restructure (#28) filed as prerequisite for Tier 2 (#9/#24-#27). Creates 3 flat files: isa.py (~400L, all constants/types/embedding/attention), executor.py (~600L, flattened NumPyExecutor/CompiledModel/TorchExecutor), programs.py (~300L, all generators). Phase files preserved as research history. Dependency chain: #28 → #24 → #25 → #26 → #27. Root cause: CCotW timed out reading 2900-line phase14 piecemeal before writing any code.

---

## 2026-03-24 — decision (p1) `df1b8fd7`
_tags: decision, architecture, issue-9_

llm-as-computer #9 (Tier 2: locals, linear memory, function calls) decomposed into 4 sub-issues #24-#27 for CCotW implementation. Decision: CCotW over Claude.ai because work is pure Python (no Mojo — that's #17), follows established phase14 patterns, and needs tight iteration loops. Chunks are dependency-ordered: locals → memory → calls → integration tests. Each has ratchet-style invariants. Architecture goes from 5 to 10 active attention heads (of 18). Issues #8 and #15 are closed/merged.

---

## 2026-03-23 — procedure (p1) `52b32878`
_tags: shipped, issue-11, arithmetic, 2026-03-23_

Phase 14 Chunk 1 (Issue #11) SHIPPED: 5 arithmetic opcodes added to llm-as-computer.

NEW OPCODES: MUL(13), DIV_S(14), DIV_U(15), REM_S(16), REM_U(17), plus OP_TRAP(99) for div-by-zero.
FILE: phase14_extended_isa.py extending Phase 13.

ARCHITECTURE DECISION — nonlinear FF dispatch:
MUL/DIV/REM can't be expressed as M_top linear routing (MUL = va*vb, not a linear combo).
Solution: M_top rows for nonlinear ops set to zero; explicit nonlinear computation in forward().
One-hot vector selects which path contributes. Clean extension of compiled transformer paradigm.

TRAP MECHANISM: OP_TRAP=99, appended as TraceStep, executor breaks. No error flags, no new mechanism.
Division semantics: _trunc_div (truncate toward zero, WASM-style), _trunc_rem (sign matches dividend).

NEW ALGORITHMS ENABLED: native multiply (4 steps vs 1109 for 7×100), factorial, GCD (Euclidean with REM_S), native is_even (6 steps vs 506 for n=100).

OPCODE_DIM_MAP: MUL→24, DIV_S→25, DIV_U→26, REM_S→27, REM_U→28 (D_MODEL=36, within range).
OPCODE_IDX: MUL→12 through REM_U→16. N_OPCODES=17.

All 10 test groups pass (87 individual tests). Full Phase 4/11/13 backward compatibility.

---

## 2026-03-23 — decision (p1) `3dcba263`
_tags: wasm, roadmap, architecture, 2026-03-23_

LLM-as-computer WASM expansion roadmap (2026-03-23):

CURRENT STATE: 12 opcodes (PUSH/POP/ADD/SUB/DUP/SWAP/OVER/ROT/JZ/JNZ/NOP/HALT). Turing-complete but toy — multiply is O(n) repeated addition, no comparisons, no bitwise ops, no local variables, no memory.

WASM 1.0 has 172 instructions across 5 categories: 13 control, 2 parametric, 5 variable, 25 memory, 127 numeric.

TIER 1 — FF dispatch only (no new attention heads):
  ~39 new opcodes: MUL/DIV/REM (6), comparisons EQ/NE/LT/GT/LE/GE/EQZ (13), bitwise AND/OR/XOR/SHL/SHR/ROTL/ROTR (14), unary CLZ/CTZ/POPCNT/ABS/NEG (5), SELECT (1).
  All are pure "pop→compute→push" — same attention mechanism, just more elif branches in FF dispatch.
  IMPACT: Native MUL alone collapses multiply(7,100) from 1109 steps to ~8.

TIER 2 — New memory spaces (same parabolic mechanism, new attention heads):
  LOCAL.GET/SET: separate "locals" parabolic space, 1 new head pair
  LOAD/STORE (linear memory): separate "heap" space, 1 new head pair. Phase 2b residual addressing → 25M range.
  CALL/RETURN: call stack for return addresses + frame pointers.
  Percepta architecture has 13 reserved heads (5 of 18 active) — plenty of headroom.

TIER 3 — Architectural extensions:
  BLOCK/LOOP/IF/ELSE/END: compile to JZ/JNZ at assembly time (assembler work, not executor)
  BR_TABLE: jump table lookup via attention
  Float ops (f32/f64): analytical compilation of float math in FF layer is harder

KEY INSIGHT: Tier 1 is the sweet spot — 39 opcodes, zero architectural changes, transforms "toy Forth" into "capable integer computer." Effort: hours. Tier 2 is the VM milestone. Tier 3 approaches real WASM compat.

---

## 2026-03-23 — procedure (p1) `45f3290c`
_tags: mojo, skill, shipped, 2026-03-23_

SHIPPED: llm-as-computer skill — functional compiled transformer executor.

WHAT: Mojo-based stack machine where every instruction fetch and stack read is a parabolic attention head (dot-product → argmax → value extraction). Full ISA: PUSH/POP/ADD/SUB/DUP/SWAP/OVER/ROT/JZ/JNZ/NOP/HALT. Python runner with built-in algorithm generators (fib, multiply, power2, sum_n).

FILES:
- /mnt/skills/user/llm-as-computer/SKILL.md
- /mnt/skills/user/llm-as-computer/executor.mojo (Mojo source, ~130 lines)
- /mnt/skills/user/llm-as-computer/run.py (Python runner + generators)

PERFORMANCE:
- fib(50) = 12,586,269,025 in 1.3ms (591 steps, 470K steps/s)
- power2(20) = 1,048,576 in 141µs (206 steps, 1.5M steps/s)
- sum(1..500) = 125,250 in 64ms (5006 steps, 78K steps/s — slows due to O(n) stack scan)

LIMITATION: Append-only stack model means stack scans grow linearly with total writes. Programs with deep loops over large accumulators (multiply(7,100), sum_n(500)) slow down. This is inherent to the attention-based memory model — could be mitigated with garbage collection of old stack entries.

NEEDS: coding-mojo skill for Mojo install. First run builds binary (~30s), subsequent calls instant.
STATUS: Working in compute environment, not yet in GitHub repo. Needs PR to persist.

---

## 2026-03-13 — analysis (p1) `45101322`
_tags: percepta, transformer-executor, architecture, research, 2026-03-13_

LLM-as-computer Phase 13 (ISA Completeness): Compiled transformer is now a general-purpose stack computer. Added SWAP, OVER, ROT opcodes (12 total), 5th attention head for SP-2. Algorithm suite all passing on both numpy + PyTorch executors with trace-level match: Fibonacci (fib(10)=55, 111 steps), multiply via repeated addition (12*10=120, 119 steps), power-of-2 via repeated doubling (2^7=128, 76 steps), sum 1..N (sum(1..15)=120, 156 steps), parity test via conditional branching. Architecture: d_model=36, 5/18 heads active, 964 compiled params. Key insight: SWAP/OVER/ROT transforms ISA from theoretically-Turing-complete to Forth-equivalent and practically programmable. Parabolic addressing generalizes cleanly to arbitrary stack depth offsets.

---

## 2026-03-13 — decision (p2) `f21caa74`
_tags: methodology, research, percepta, correction, 2026-03-13_

METHODOLOGICAL LESSON (llm-as-computer): When replicating/testing claims from an external resource (blog post, paper, etc.), do an extractive summary of ALL specifics from the original and store it with the iterative plan. This prevents drift from the original problem. Concrete example: Phases 5-10 tried to TRAIN arithmetic into the model via gradient descent, while Percepta's core insight was to COMPILE logic into weights. We spent 5 phases on a path the blog post explicitly said wouldn't work. Phase 11 returned to the compile path and immediately succeeded. The drift happened because we didn't anchor our plan to the specific claims of the source.

---

## 2026-03-12 — procedure (p1) `3f5d01a1`
_tags: curriculum-learning, research, 2026-03-12_

PLAN: LLM-as-computer Phase 6 — Curriculum Learning

HYPOTHESIS: Phase 5's 56% accuracy gap is because the model must simultaneously learn state tracking AND arithmetic. Curriculum learning decomposes this — teach tracking first, arithmetic last.

STAGES:

Stage 1: PUSH + HALT only
  - Programs: PUSH x, PUSH y, ..., HALT (3-8 instructions)
  - What model learns: opcode prediction, SP always increments by 1, TOP = last pushed value
  - This is near-trivial — establishes baseline weights for token embedding, position encoding
  - Success: >95% token accuracy
  - Data: 1000 train / 150 val / 50 test, max_push_val=50

Stage 2: PUSH + POP + DUP + HALT (all non-arithmetic ops)
  - Initialize from Stage 1 checkpoint
  - Programs: mix of PUSH/POP/DUP with validity constraints
  - What model learns: SP can decrement (POP), TOP can come from stack recall (POP/DUP)
  - Harder than Stage 1 because TOP after POP requires attending to earlier stack state
  - Success: >85% token accuracy
  - Data: 1000 train / 150 val / 50 test

Stage 3: Full instruction set (add ADD)
  - Initialize from Stage 2 checkpoint
  - Programs: same distribution as Phase 5 (all ops valid)
  - What model learns: ADD requires reading two stack values and computing their sum
  - This is the hardest stage — the arithmetic gap from Phase 5
  - Success: >70% token accuracy AND at least 1 perfect trace
  - Data: 1000 train / 150 val / 50 test, max_push_val=30 (keep sums in range)

IMPLEMENTATION:

Single new file: phase6_curriculum.py
  - Reuses Phase 5 model architecture (MicroTransformer, d=64, h=4, L=2, 137K params)
  - Reuses Phase 5 encoding/decoding, TraceDataset
  - New: constrained_random_program(allowed_ops=[...]) for stage-specific data gen
  - New: checkpoint save/load functions with stage metadata
  - New: stage runner that trains, evaluates, saves, and prints metrics

EXECUTION PROTOCOL (per the iterative-container-work ops config):
  1. Write phase6_curriculum.py → push to GitHub immediately
  2. Run Stage 1 → push checkpoint metrics to GitHub (or memory if >5MB)
  3. Run Stage 2 → push
  4. Run Stage 3 → push
  5. Update FINDINGS.md with results → push
  6. Update stash

CHECKPOINT FORMAT:
  {model_state_dict, optimizer_state_dict, stage, epoch, metrics_history, best_val_acc}
  Saved as phase6_checkpoint_stageN.pt locally
  Metrics summary pushed to GitHub as phase6_results.json

RISK: Container timeout. Mitigations:
  - Each bash call trains max 30 epochs (estimated ~120s for 1000 samples)
  - Checkpoint saved BEFORE evaluation (eval can be re-run)
  - If approaching 180s, stop early and save
  - Resume from checkpoint in next bash call

COMPARISON TO PHASE 5 BASELINE:
  Phase 5 best: 56% token accuracy, 0/50 perfect traces (all ops from scratch)
  If curriculum Stage 3 exceeds this, curriculum learning is validated
  If not, the bottleneck is model capacity, not training order

WHAT THIS DOESN'T TEST:
  - Larger models (needs GPU)
  - Whether the model discovers parabolic encoding (needs attention visualization)
  - WASM fragment execution (Phase 7, needs much bigger model)

---
