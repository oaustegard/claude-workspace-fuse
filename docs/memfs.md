# Muninn memory filesystem (`/mnt/muninn/`)

A read-only FUSE filesystem that projects Muninn's active Turso memories
as individual markdown files, so any Unix tool that operates on paths
(grep, find, wc, the harness Read tool, tree-sitting, etc.) can work
across the whole corpus without per-call SQL or custom Python.

## Why

Calling `recall()` from Python returns one memory at a time. That makes
bulk operations expensive enough that I almost never reach for them —
"have I written about X before?" loses to "I'll just rederive it." The
filesystem projection inverts that: searching 1,500 memories is one
`grep` away.

Validated against the principle Turso themselves landed on in
[AgentFS](https://turso.tech/blog/agentfs-fuse) — *"many AI coding
agents already work natively with a filesystem, with the foundational
models having a good grasp of Unix tools."* Same idea, applied
specifically to my existing Turso memory schema.

## Layout

```
/mnt/muninn/
├── README.md                          — live status (count, last refresh)
└── memories/
    ├── 000ea49a-created-cloudflare-worker-strudel-cdn-at.md
    ├── 00361f7a-topics-openai-dod-contract-anthropic-com.md
    ├── ...
    └── ffeeddcc-last-memory-here.md
```

Each file's name is `<8-char-id-prefix>-<slug>.md`. The body is a small
markdown render of the memory: type, created_at, tags, priority as a
header, then the summary text.

Only memories with `deleted_at IS NULL AND is_superseded = 0` are
exposed. Tombstoned and superseded memories are skipped.

## Architecture

```
boot-ccotw.sh
  ├── (existing phases: skills_fetch, muninn_utilities, python_paths, ...)
  ├── _install_fuse_deps              — apt: libfuse2 fuse; pip: fusepy
  └── _start_memfs_background         — nohup scripts/muninn_memfs.py /mnt/muninn

scripts/muninn_memfs.py (single process, lives for the session)
  ├── bootstrap thread                — SELECT id, summary, type, tags, created_at, priority
  │                                     FROM memories WHERE deleted_at IS NULL
  │                                     AND is_superseded = 0   (~700ms over hosted Turso)
  ├── refresh thread                  — same query every REFRESH_INTERVAL (default 300s)
  └── FUSE Operations subclass        — getattr/readdir/read against an in-memory dict
                                        protected by a threading.Lock
```

No SQLite, no libsql sync, no container-layer SNAPSHOT bloat. The whole
working set is ~7 MB of summary text in process memory.

## Performance (measured, 2026-05-17)

| Operation | Latency | Notes |
|-----------|---------|-------|
| Bootstrap query | 541–705 ms | `SELECT id,summary,type,tags,created_at,priority` over 1,486 active rows |
| `ls /mnt/muninn/memories/` | 6 ms | 1,486 entries |
| `cat /mnt/muninn/memories/<one>.md` | <1 ms | served from in-memory dict |
| `grep -l 'fuse' /mnt/muninn/memories/*.md` | 668 ms | full-corpus scan, ~1,486 file opens through FUSE |
| Refresh tick | ~700 ms every 300s | full re-pull, replaces state under lock |

The bootstrap happens in parallel with the rest of `boot-ccotw.sh`, so
it's hidden behind ~5–10 seconds of existing dead time before the
first user prompt. First-read blocking only kicks in if Muninn reaches
for memories immediately after boot, which is rare.

## Why not <X>

**Why not libsql sync to a local mirror?** Tried it. `libsql_experimental`
cold-sync is ~14s (page-level replication of a 130 MB DB including FTS5
indices and tag_cooccurrence we don't need). `libsql` 0.1.11 is only
~20% faster — the CDC sync from the
[Turso Sync benchmark](https://turso.tech/blog/sync-benchmark)
isn't wired up in the Python bindings yet. A targeted
`SELECT id,summary,type,tags,created_at,priority FROM memories` over
hosted Turso pulls the same content in ~540ms.

**Why not snapshot the local DB into the container layer?** Considered.
Would work, but adds ~50 MB to the layer tarball and creates a stale-
snapshot dependency on layer-rebuild cadence. The bootstrap is fast
enough that this complexity isn't justified.

**Why not write support?** Footgun risk —
`echo "..." > /mnt/muninn/memories/new.md` is too easy to do by
accident. Writes still go through `remember()` directly. May revisit if
a clear use case emerges.

**Why not preserve FTS5 search?** Hosted Turso has the FTS5 indices
already. For explicit FTS queries, one-shot remote queries
(`_exec("SELECT ... WHERE summary MATCH 'foo'")`) take ~150ms — better
than the cost of replicating the indices locally. For substring scans,
`grep` over 1,486 files is 668ms, which is fast enough.

## Manual operations

Mount (normally done by `boot-ccotw.sh`):
```bash
python3 scripts/muninn_memfs.py /mnt/muninn &
```

Unmount cleanly:
```bash
fusermount -u /mnt/muninn
```

Force-refresh (kill + relaunch — currently no SIGHUP handler):
```bash
fusermount -u /mnt/muninn
python3 scripts/muninn_memfs.py /mnt/muninn &
```

Override the refresh interval:
```bash
MUNINN_MEMFS_REFRESH=60 python3 scripts/muninn_memfs.py /mnt/muninn &
```

Inspect the process log:
```bash
tail -f /tmp/.muninn-memfs.log
```

## Tests

```bash
python3 -m pytest tests/test_muninn_memfs.py -v
```

26 unit tests. `scripts.turso._exec` is mocked at import time, so the
tests don't touch a real Turso DB and don't need a FUSE mount. They
cover: slugification, memory formatting, bootstrap behavior, bootstrap
failure recovery, all FUSE ops (getattr/readdir/open/read), and the
read-blocks-until-bootstrap-completes invariant.
