# Experiments

Ad-hoc evals and one-off explorations run in CCotw sessions. Each row links to
its writeup.

| Date | Experiment | Summary |
|---|---|---|
| 2026-07-06 | [fuse-vs-http-eval](fuse-vs-http-eval/RESULTS.md) | Benchmarked the `/mnt/muninn` FUSE mount vs HTTP `recall()`. Single-memory read ~96× faster (7 ms vs 672 ms); multi-memory workflows ~40× vs naive per-read HTTP; `grep` exhaustive where `recall()` FTS5 returns 15/46. Bulk one-shot scan slightly slower than server-side SQL `LIKE`. Verdict: latency+ergonomics+correctness win, staleness/read-only tradeoff worth it. Also diagnosed a total boot failure (codeload 403 lockdown killing the container-layer bootstrap under `set -e`). |
