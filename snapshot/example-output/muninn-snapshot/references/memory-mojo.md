---
tag: mojo
memory_count: 3
date_range: 2026-03-23 to 2026-04-14
---

# mojo

_3 memories from Muninn's past, primary tag `mojo`._

## 2026-04-14 — decision (p1) `c8b0f060`
_tags: coding-mojo, bug, workaround, linker_

Mojo build -lm workaround: `mojo build file.mojo -Xlinker -lm` fixes the linker error when using std.math functions (exp, log, sin, cos, sqrt, atan2). Known bug: github.com/modular/modular/issues/5925 (open since 2026-02-09). mojo run (JIT) works without the flag. Small programs may work without it if LLVM constant-folds the math calls at compile time.

---

## 2026-03-24 — procedure (p1) `7e8e479f`
_tags: coding-mojo, modular, install, optimization, container_

MOJO SLIM INSTALL: `pip install modular --no-deps && pip install mojo max` skips ~350MB of unnecessary ML deps (transformers 104M, pyarrow 147M, datasets, grpcio, opentelemetry, fastapi, etc). The bloat comes from `modular` requiring `max[benchmark]` and `max[serve]` extras. The compiler binary (1.1GB, unavoidable) lives in `modular/bin/mojo`. Base deps (numpy, pyyaml, rich) come via `max` without extras. Updated in llm-as-computer skill setup.sh and runner.py. Should also update coding-mojo skill (issue needed).

---

## 2026-03-23 — experience (p0) `d270960b`
_tags: modular, experiment, programming-languages, 2026-03-23_

First Mojo experiment in Claude.ai container: installed Modular 26.2 (mojo 0.26.2), wrote and ran programs exercising structs, SIMD, comptime for, and benchmarks. Key 26.2 changes learned from compiler errors: std. prefix required for imports (from std.math), comptime for replaces @parameter for, String() constructor instead of str(). Benchmarked fibonacci and mandelbrot vs CPython — 96x and 19x speedup respectively on vanilla scalar code. [REDACTED] has been tracking Mojo from a distance, attracted to Python-like syntax with strong types.

---
