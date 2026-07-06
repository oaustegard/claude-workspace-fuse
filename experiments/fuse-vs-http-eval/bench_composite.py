#!/usr/bin/env python3
"""Composite workflow: find memories about X, then read them all."""
import subprocess, sys, time, statistics, json
sys.path.insert(0, "/mnt/skills/user/remembering")
from scripts.turso import _exec

MOUNT = "/mnt/muninn/memories"
ACTIVE = "deleted_at IS NULL AND is_superseded = 0"

def bash(cmd):
    t0 = time.perf_counter()
    r = subprocess.run(["bash","-c",cmd], capture_output=True, text=True)
    return (time.perf_counter()-t0)*1000, r.stdout, r.stderr

def timed(fn):
    t0 = time.perf_counter(); out = fn(); return (time.perf_counter()-t0)*1000, out

def med(fn, iters):
    s=[]; last=None
    for _ in range(iters):
        dt,out=fn(); s.append(dt); last=out
    return round(statistics.median(s),1), round(min(s),1), round(max(s),1), last

results={}
print("=== COMPOSITE: find + read every memory mentioning 'fuse' (46 matches) ===")

# FUSE: grep -l to find, then cat each file, all native shell
def fuse_workflow():
    dt,out,_ = bash(f"for f in $(grep -lri 'fuse' {MOUNT}/); do cat \"$f\"; done | wc -c")
    return dt, out.strip()
m = med(fuse_workflow, 5)
print(f"  FUSE grep-l + cat-each (one shell line)   median={m[0]:8.1f}ms  [{m[1]}–{m[2]}]  → {m[3]} bytes")
results["fuse_workflow"]={"median":m[0],"min":m[1],"max":m[2]}

# HTTP savvy: one SQL round-trip returns id + full content for all matches
def http_savvy():
    rows=_exec(f"SELECT id, summary FROM memories WHERE {ACTIVE} AND lower(summary) LIKE '%fuse%'")
    return sum(len(r['summary']) for r in rows)
m = med(lambda: timed(http_savvy), 5)
print(f"  HTTP 1x SQL LIKE (id+content in one trip)  median={m[0]:8.1f}ms  [{m[1]}–{m[2]}]  → {m[3]} chars")
results["http_savvy_sql"]={"median":m[0],"min":m[1],"max":m[2]}

# HTTP naive: recall() to find, then one _exec per memory to read full content
def http_naive():
    ids=_exec(f"SELECT id FROM memories WHERE {ACTIVE} AND lower(summary) LIKE '%fuse%'")
    total=0
    for r in ids[:10]:  # cap at 10 to keep runtime sane; extrapolate
        row=_exec(f"SELECT summary FROM memories WHERE id = '{r['id']}'")
        total+=len(row[0]['summary']) if row else 0
    return total
m = med(lambda: timed(http_naive), 3)
print(f"  HTTP per-memory round-trip (10 of 46)      median={m[0]:8.1f}ms  [{m[1]}–{m[2]}]  (×4.6 for all 46 ≈ {m[0]*4.6:.0f}ms)")
results["http_naive_perread"]={"median":m[0],"min":m[1],"max":m[2],"note":"10 of 46 reads; full set ~4.6x"}

# ── FUSE read throughput: cat ALL 2085 files ──
print("\n=== FUSE read-path throughput (read every file) ===")
def cat_all():
    dt,out,_=bash(f"cat {MOUNT}/*.md | wc -c")
    return dt,out.strip()
m=med(cat_all,3)
per=m[0]/2085
print(f"  cat all 2085 files                         median={m[0]:8.1f}ms  → {per:.3f}ms/file FUSE-read overhead")
results["fuse_cat_all"]={"median":m[0],"per_file_ms":round(per,3),"bytes":m[3]}

print("\n"+json.dumps(results,indent=2))
with open("/home/user/claude-workspace-fuse/scratch_bench2_results.json","w") as f:
    json.dump(results,f,indent=2)
