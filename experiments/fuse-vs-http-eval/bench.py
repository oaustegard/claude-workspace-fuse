#!/usr/bin/env python3
"""FUSE mount vs HTTP recall() benchmark. Same perf_counter clock for both paths."""
import subprocess, sys, time, statistics, json
sys.path.insert(0, "/mnt/skills/user/remembering")
from scripts.turso import _exec

MOUNT = "/mnt/muninn/memories"
ACTIVE = "deleted_at IS NULL AND is_superseded = 0"

def bash(cmd):
    t0 = time.perf_counter()
    r = subprocess.run(["bash","-c",cmd], capture_output=True, text=True)
    dt = (time.perf_counter()-t0)*1000
    return dt, r.stdout, r.stderr

def timed(fn, *a, **k):
    t0 = time.perf_counter()
    out = fn(*a, **k)
    return (time.perf_counter()-t0)*1000, out

def stats(samples):
    return {"median": round(statistics.median(samples),1),
            "min": round(min(samples),1), "max": round(max(samples),1),
            "n": len(samples)}

def run_many(label, fn, iters):
    samples, last = [], None
    for _ in range(iters):
        dt, out = fn()
        samples.append(dt); last = out
    s = stats(samples)
    print(f"  {label:42s} median={s['median']:8.1f}ms  [{s['min']:.1f}–{s['max']:.1f}]  n={s['n']}")
    return s, last

results = {}

# ── Benchmark 1: bulk substring search "which memories mention 'fuse'" ──
print("\n=== B1: bulk substring — 'which memories mention fuse' ===")
# FUSE grep (subprocess, includes spawn — the real ergonomic cost)
def fuse_grep():
    dt, out, _ = bash(f"grep -lri 'fuse' {MOUNT}/")
    return dt, len(out.strip().splitlines())
s, cnt = run_many("FUSE: grep -lri 'fuse'", fuse_grep, 5)
results["b1_fuse_grep"] = {**s, "matches": cnt}
print(f"    → {cnt} files matched")

# HTTP SQL LIKE (server-side substring, exhaustive) — warm in-process
def http_like():
    rows = _exec(f"SELECT id FROM memories WHERE {ACTIVE} AND lower(summary) LIKE '%fuse%'")
    return len(rows)
s, cnt = run_many("HTTP: _exec LIKE '%fuse%'", lambda: timed(http_like), 5)
results["b1_http_like"] = {**s, "matches": cnt}
print(f"    → {cnt} rows matched")

# HTTP pull-all + python substring (replicate grep semantics client-side)
def http_pull_grep():
    rows = _exec(f"SELECT id, summary FROM memories WHERE {ACTIVE}")
    return sum(1 for r in rows if 'fuse' in (r.get('summary') or '').lower())
s, cnt = run_many("HTTP: pull-all + py substring", lambda: timed(http_pull_grep), 3)
results["b1_http_pull"] = {**s, "matches": cnt}
print(f"    → {cnt} rows matched")

# HTTP recall() — the ergonomic Muninn way (FTS5 ranked, needs high n for exhaustive)
try:
    from scripts.memory import recall
    def http_recall():
        return len(recall(search='fuse', n=2000, raw=True))
    s, cnt = run_many("HTTP: recall(search='fuse', n=2000)", lambda: timed(http_recall), 3)
    results["b1_http_recall"] = {**s, "matches": cnt}
    print(f"    → {cnt} results (FTS5 ranked — semantics differ from substring)")
except Exception as e:
    print(f"  recall() unavailable: {e!r}")
    results["b1_http_recall"] = {"error": repr(e)}

# ── Benchmark 2: multi-pattern grep ──
print("\n=== B2: multi-pattern — tree-sitter|mojo|fuse ===")
def fuse_multi():
    dt, out, _ = bash(f"grep -lriE 'tree-sitter|mojo|fuse' {MOUNT}/")
    return dt, len(out.strip().splitlines())
s, cnt = run_many("FUSE: grep -lriE 'tree-sitter|mojo|fuse'", fuse_multi, 5)
results["b2_fuse_multi"] = {**s, "matches": cnt}
print(f"    → {cnt} files matched")

def http_multi():
    rows = _exec(f"""SELECT id FROM memories WHERE {ACTIVE} AND
        (lower(summary) LIKE '%tree-sitter%' OR lower(summary) LIKE '%mojo%' OR lower(summary) LIKE '%fuse%')""")
    return len(rows)
s, cnt = run_many("HTTP: _exec 3x LIKE (OR)", lambda: timed(http_multi), 5)
results["b2_http_multi"] = {**s, "matches": cnt}
print(f"    → {cnt} rows matched")

# ── Benchmark 3: single memory read ──
print("\n=== B3: single memory read (id 06ea5a6d) ===")
def fuse_cat():
    dt, out, _ = bash(f"cat {MOUNT}/06ea5a6d-*.md")
    return dt, len(out)
s, nbytes = run_many("FUSE: cat 06ea5a6d-*.md", fuse_cat, 5)
results["b3_fuse_cat"] = {**s, "bytes": nbytes}

def http_read():
    rows = _exec(f"SELECT id, summary, type, tags, created_at, priority FROM memories WHERE id LIKE '06ea5a6d%'")
    return len(rows[0]['summary']) if rows else 0
s, nb = run_many("HTTP: _exec WHERE id LIKE '06ea5a6d%'", lambda: timed(http_read), 5)
results["b3_http_read"] = {**s, "summary_bytes": nb}

# ── Benchmark 4: corpus-wide wc -l ──
print("\n=== B4: corpus-wide wc -l (line count of every memory) ===")
def fuse_wc():
    dt, out, _ = bash(f"wc -l {MOUNT}/*.md | tail -1")
    return dt, out.strip()
s, total = run_many("FUSE: wc -l *.md", fuse_wc, 5)
results["b4_fuse_wc"] = {**s, "total_line": total}
print(f"    → {total}")

def http_wc():
    rows = _exec(f"SELECT summary FROM memories WHERE {ACTIVE}")
    # format_memory adds a header (~8-10 lines) + body; wc counts rendered file lines.
    # Approximate body line count for parity of the *data movement* cost:
    return sum((r.get('summary') or '').count('\n')+1 for r in rows)
s, tl = run_many("HTTP: pull-all + py count lines", lambda: timed(http_wc), 3)
results["b4_http_wc"] = {**s, "total_body_lines": tl}
print(f"    → ~{tl} body lines (excl. rendered headers)")

print("\n=== JSON ===")
print(json.dumps(results, indent=2))
with open("/home/user/claude-workspace-fuse/scratch_bench_results.json","w") as f:
    json.dump(results, f, indent=2)
