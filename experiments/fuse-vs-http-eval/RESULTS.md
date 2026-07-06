# FUSE mount vs HTTP `recall()` — effectiveness eval

**Date**: 2026-07-06 · **Session**: turso-fuse-mount-test · **Corpus**: 2085 active
memories · **Mount**: `/mnt/muninn` (`scripts/muninn_memfs.py`, `REFRESH_INTERVAL=300s`)

## TL;DR

Projecting Turso memories as files is a **real win — but not the one the pitch
implies.** The mount does *not* make bulk substring scanning faster; a
server-side SQL `LIKE` beats `grep` on raw wall-clock. What the mount actually
delivers:

1. **Single-memory reads are ~96× faster** — `cat` a memory file: **7 ms** vs
   **672 ms** for an HTTP `_exec`/`recall`. No network per read; served from an
   in-memory dict once bootstrapped.
2. **Any multi-memory workflow collapses from tens of seconds to sub-second.**
   "Find + read every memory about X" the naive HTTP way (recall, then read each)
   ran **~7.4 s for 10 reads (→ ~34 s for all 46)**; the FUSE `grep -l | cat`
   one-liner did the full set in **824 ms** — **~40×**.
3. **`grep` is exhaustive; `recall()` is not.** `grep -lri 'fuse'` found **46**
   memories. `recall(search='fuse')` (FTS5, ranked) returned **15**. To match
   grep's completeness over HTTP you must hand-write SQL `LIKE` — exactly the
   custom query the mount exists to avoid.
4. **Ergonomics**: native Unix tools compose (`grep | wc`, `xargs`, `sort`,
   `sed`) with zero schema knowledge and zero Python.

The one thing the mount does **not** win: a single-pass bulk scan. Server-side
`LIKE` ships only matched rows; FUSE must stream all 2085 files back through
per-file upcalls (~0.40 ms/file ≈ 835 ms floor). So `grep` on the mount is
*slightly slower* than SQL `LIKE` for one-shot search — but it's exhaustive,
composable, and needs no query.

**Verdict: worth it.** The staleness (≤5 min) and read-only limits sit exactly
where they don't hurt — the mount targets the *established* corpus for read/search;
writes and read-your-own-writes correctly stay on the live HTTP path.

---

## Boot did NOT run cleanly — and the reason matters

The prior session's hypothesis (three co-equal repo sources → session rooted at
`/home/user` → no repo's SessionStart hook fired) was **fixed**: this session
had only `claude-workspace-fuse` as its source, `pwd` was correctly inside the
repo, and the hook **did** fire.

But boot still **failed entirely** — a *different* failure mode:

- The agent proxy is in lockdown: `codeload.github.com` returns **403 for
  out-of-scope repos** (`claude-skills`, `muninn-utilities`) and **200 only for
  the in-scope repo**.
- Boot's very first fetch, `_refresh_container_layer_skill` (`boot-ccotw.sh:379`),
  does `curl -sL <claude-skills tarball> | tar -xz` with **no fallback**, under
  `set -e`. The 403 body pipes into `tar`, `tar` fails, and `set -e` kills boot
  **before composing a single layer**.
- Fallout: no `fuse` layer (no `fusermount`, no `libfuse.so.2`, no `fusepy`), no
  skills, no `remembering`, no `httpx` — the mount never mounted. The boot log
  dead-ends at exactly `Fetching container-layer skill...`.
- The mirror-branch fallbacks the *later* steps rely on (`mirror/skills`,
  `mirror/muninn-utilities`) **don't exist on origin** (`git ls-remote origin
  'refs/heads/mirror/*'` → empty), so even reaching them wouldn't have helped.

### Manual recovery (what it took to run this eval)

| Step | Command | Result |
|---|---|---|
| System FUSE libs | `apt-get install -y fuse libfuse2` | ✓ `fusermount` + `libfuse.so.2` |
| Widen scope | `add_repo oaustegard/muninn-utilities` | ✓ codeload → 200 |
| Python deps | `pip install fusepy requests` | ✓ (PyPI reachable via proxy) |
| Fetch `remembering/` | codeload muninn-utilities tarball → `/mnt/skills/user/remembering` | ✓ `_exec` live |
| Start mount | `python3 scripts/muninn_memfs.py /mnt/muninn` | ✓ 2085 files, bootstrap 2269 ms |

**Actionable fixes for boot** (not applied here — eval-only branch):
1. Give `_refresh_container_layer_skill` the same codeload→mirror fallback the
   skill/utility fetches have, and don't let it run naked under `set -e`.
2. Actually populate the `mirror/*` branches (the workflow that should maintain
   them isn't producing them), or drop the dead fallback.
3. `_verify_fuse_deps` correctly *warns* but boot dies long before it runs, so the
   warning never surfaces.

---

## Methodology

Same `time.perf_counter()` clock for both paths (`scratch_bench.py`,
`scratch_bench2.py`). FUSE ops run as real subprocesses (`grep`/`cat`/`wc` —
spawn cost included, since that's the true ergonomic cost). HTTP ops call
`_exec` warm, in-process (best case for HTTP — no interpreter startup). This
bias *favors HTTP*, which makes the FUSE read-latency win conservative.
Median of 3–5 runs; `[min–max]` shown.

The corpus at eval time was **2085 active memories** (CLAUDE.md's "1490+" is
stale — corpus has grown).

## Results

| # | Operation | FUSE (native tools) | HTTP (Turso) | Winner |
|---|---|---|---|---|
| B1 | Substring search `'fuse'` (exhaustive) | `grep -lri`: **741 ms** → 46 | `_exec LIKE`: **551 ms** → 46 · `recall()`: 619 ms → **only 15** | HTTP on speed; FUSE on completeness+ergonomics |
| B2 | Multi-pattern `tree-sitter\|mojo\|fuse` | `grep -lriE`: **821 ms** → 105 | `_exec` 3×LIKE: **660 ms** → 104 | HTTP on speed; FUSE on ergonomics |
| B3 | **Single memory read** | `cat`: **7.0 ms** | `_exec` by id: **672 ms** | **FUSE ~96×** |
| B4 | Corpus-wide `wc -l` | `wc -l *.md`: **801 ms** | pull-all + py count: **919 ms** | FUSE (speed + ergonomics) |
| C | **Find + read all 46 `'fuse'` memories** | `grep -l \| cat`: **824 ms** | 1× SQL (id+content): 679 ms · naive per-read loop: **~34 s** | FUSE vs naive **~40×**; SQL-savvy HTTP ties |

FUSE read-path throughput: **0.401 ms/file** (all 2085 files `cat`'d in 835 ms) —
this per-file upcall cost is the floor under every corpus-wide FUSE op and the
reason bulk `grep` can't beat server-side `LIKE`.

## Analysis by operation

**Bulk substring search (B1/B2).** HTTP wins raw speed because SQLite scans
server-side and ships only matches, while FUSE streams *every* file back through
kernel↔python upcalls. But two things flip the practical calculus toward FUSE:
(a) `grep` is **exhaustive substring**; the ergonomic HTTP path `recall()` is
FTS5-**ranked and capped** and returned 15/46 — silently incomplete. Matching
grep over HTTP means hand-writing `LIKE` SQL and knowing the schema. (b) `grep`
composes — `grep -l … | xargs wc -l | sort -n` is one line; the SQL equivalent
is a program.

**Single-memory read (B3).** The unambiguous, decisive win. **7 ms vs 672 ms
(~96×).** Post-bootstrap, a file read is an in-memory dict lookup plus FUSE
overhead; HTTP is a full Turso round-trip every time. This is the pattern that
dominates real agent usage — the `Read` tool on a memory file, `cat`, `head`,
opening a handful of candidates.

**Multi-memory workflows (C).** This is where the mount earns its keep. The
naive HTTP loop (recall → read each) is **~739 ms/memory** → ~34 s for 46. FUSE's
`grep -l | cat` does the whole set in **824 ms (~40×)**. A SQL-savvy caller who
folds content into one `LIKE` round-trip (679 ms) ties FUSE on this specific
shape — but only by writing SQL, and only when the whole result fits one query;
the moment you want to pipe bodies through `wc`/`sort`/`sed`, you're back in
Python while FUSE stays in the shell.

**Corpus aggregation (B4).** `wc -l *.md` (801 ms) beats pull-all-and-count
(919 ms) and needs no code. Line counts differ (55 859 rendered-file lines vs
37 856 body lines) because the mount renders each memory with a markdown header.

## Staleness / read-only tradeoff

- **Staleness ≤ `REFRESH_INTERVAL` (300 s).** A memory written seconds ago won't
  appear until the next background refresh. Bounded and acceptable: the mount is
  for the *established* corpus. For read-your-own-writes, use `recall()` (live).
- **Read-only by design.** Writes go through `remember()` (HTTP → Turso). The
  mount refuses write/create flags (`EROFS`). Correct separation of concerns.
- **Bootstrap cost** ~2.3 s one-time at mount (hidden behind CCotw startup dead
  time); refreshes are the same ~2.3 s every 300 s in a background thread.

## Bottom line

Does projecting Turso memories as files beat HTTP `recall()`? **Yes, for the
operations that matter** — per-read latency (~96×) and multi-memory workflows
(~40× vs the naive path) — plus native-tool ergonomics and exhaustive-by-default
search semantics that `recall()`'s FTS5 ranking silently lacks. It does **not**
win raw single-pass bulk-scan throughput (server-side `LIKE` is faster there),
so the mount is a **latency + ergonomics + correctness** win, not a scan-speed
one. The staleness (≤5 min) and read-only constraints land precisely where the
mount is designed not to be used for writes, so the tradeoff is worth it.

*Caveat: measured on one container, one corpus size (2085), warm HTTP. The
FUSE read-latency advantage is structural (no network) and will hold; the
bulk-scan numbers are close enough (±30%) that corpus growth or Turso latency
could shift the exact crossover.*
