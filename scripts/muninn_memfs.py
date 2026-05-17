#!/usr/bin/env python3
"""FUSE filesystem exposing Muninn's Turso memories as files.

Mount layout:
    /mnt/muninn/
        README.md                        — status + usage notes
        memories/<8charid>-<slug>.md     — one file per active memory

Memories are pulled once at startup (bootstrap, ~540ms for 3.5k rows) and
refreshed every REFRESH_INTERVAL seconds in a background thread. Reads
before the bootstrap completes block on a threading.Event.

Read-only. Mount via:
    python3 scripts/muninn_memfs.py /mnt/muninn

Unmount via:
    fusermount -u /mnt/muninn
"""

from __future__ import annotations

import errno
import os
import re
import stat
import sys
import threading
import time
from datetime import datetime, timezone

from fuse import FUSE, FuseOSError, Operations

# Make the remembering skill importable. Boot script sets this up via a .pth
# file but we add the path defensively in case the script is run standalone.
sys.path.insert(0, "/mnt/skills/user/remembering")
from scripts.turso import _exec  # noqa: E402

REFRESH_INTERVAL = int(os.environ.get("MUNINN_MEMFS_REFRESH", "300"))
BOOTSTRAP_TIMEOUT = 30  # seconds reads will wait for first bootstrap

# Pull only what FUSE needs: identity, content, classification, recency, priority.
# Skips heavy/unneeded columns (refs, confidence, access_count, etc).
BOOTSTRAP_QUERY = """
    SELECT id, summary, type, tags, created_at, priority
    FROM memories
    WHERE deleted_at IS NULL AND is_superseded = 0
    ORDER BY created_at DESC
"""


def slugify(text: str, max_len: int = 40) -> str:
    """Filesystem-safe slug from a memory summary's first line."""
    first_line = (text or "").split("\n", 1)[0]
    cleaned = re.sub(r"[^\w\s-]", "", first_line[:120])
    slug = re.sub(r"\s+", "-", cleaned.strip()).lower()
    return slug[:max_len] or "untitled"


def format_memory(row: dict) -> bytes:
    """Render a memory row as a markdown document."""
    lines = [
        f"# {row['id']}",
        "",
    ]
    meta = []
    if row.get("type"):
        meta.append(f"**Type**: `{row['type']}`")
    if row.get("created_at"):
        meta.append(f"**Created**: {row['created_at']}")
    pr = row.get("priority")
    if pr is not None and str(pr) not in ("0", "None"):
        meta.append(f"**Priority**: {pr}")
    if row.get("tags"):
        meta.append(f"**Tags**: `{row['tags']}`")
    if meta:
        lines.append("  \n".join(meta))
        lines.extend(["", "---", ""])
    lines.append(row.get("summary", "") or "")
    return ("\n".join(lines) + "\n").encode("utf-8")


class MemFs(Operations):
    def __init__(self) -> None:
        # `entries` maps relative filename → {row, bytes}. Bytes are cached so
        # that getattr (which reports st_size) and read return identical content
        # even if a refresh fires between calls — preventing short-read EIO.
        self.entries: dict[str, dict] = {}
        self.ready = threading.Event()
        self.last_refresh: float | None = None
        # Named `_entries_lock` (not `lock`) because Operations.lock is the
        # FUSE POSIX flock op — a member named `self.lock` shadows it with a
        # threading.Lock instance and breaks any kernel-issued lock request.
        self._entries_lock = threading.Lock()
        self._stderr("starting bootstrap thread")
        threading.Thread(target=self._bootstrap, daemon=True).start()
        threading.Thread(target=self._refresh_loop, daemon=True).start()

    @staticmethod
    def _stderr(msg: str) -> None:
        sys.stderr.write(f"[memfs {time.strftime('%H:%M:%S')}] {msg}\n")
        sys.stderr.flush()

    def _pull_and_index(self) -> dict[str, dict]:
        t0 = time.perf_counter()
        rows = _exec(BOOTSTRAP_QUERY)
        new_entries: dict[str, dict] = {}
        seen: dict[str, int] = {}
        for r in rows:
            rid = r.get("id")
            if not rid:
                continue
            slug = slugify(r.get("summary", ""))
            base = f"{rid[:8]}-{slug}"
            # Disambiguate the rare collision where two memories share an 8-char
            # id prefix AND produce the same slug. (Truly rare with random
            # UUIDs, but cheap to guard.)
            n = seen.get(base, 0)
            seen[base] = n + 1
            fname = f"{base}.md" if n == 0 else f"{base}-{n}.md"
            new_entries[fname] = {"row": r, "bytes": format_memory(r)}
        self._stderr(
            f"pulled {len(new_entries)} memories in {(time.perf_counter()-t0)*1000:.0f}ms"
        )
        return new_entries

    def _bootstrap(self) -> None:
        try:
            entries = self._pull_and_index()
            with self._entries_lock:
                self.entries = entries
                self.last_refresh = time.time()
            self.ready.set()
        except Exception as exc:
            self._stderr(f"BOOTSTRAP FAILED: {exc!r}")
            # Still set ready so reads return ENOENT rather than blocking forever.
            self.ready.set()

    def _refresh_loop(self) -> None:
        while True:
            time.sleep(REFRESH_INTERVAL)
            try:
                entries = self._pull_and_index()
                with self._entries_lock:
                    self.entries = entries
                    self.last_refresh = time.time()
            except Exception as exc:
                self._stderr(f"refresh failed: {exc!r}")

    # ── Helpers ──

    def _readme_bytes(self) -> bytes:
        with self._entries_lock:
            n = len(self.entries)
            last = self.last_refresh
        last_str = (
            datetime.fromtimestamp(last, tz=timezone.utc).isoformat()
            if last
            else "pending"
        )
        body = (
            "# /mnt/muninn — Muninn memory filesystem\n\n"
            f"- **Memories indexed**: {n}\n"
            f"- **Last refresh (UTC)**: {last_str}\n"
            f"- **Refresh interval**: {REFRESH_INTERVAL}s\n\n"
            "## Layout\n\n"
            "    memories/<8charid>-<slug>.md   — one file per active memory\n\n"
            "## Usage\n\n"
            "    grep -lr 'fuse' /mnt/muninn/memories/\n"
            "    cat /mnt/muninn/memories/0d63ed4f-*.md\n"
            "    wc -l /mnt/muninn/memories/*.md | tail -1\n\n"
            "Memories pulled by `SELECT id, summary, type, tags, created_at, priority\n"
            "FROM memories WHERE deleted_at IS NULL AND is_superseded = 0`.\n"
            "Read-only. To write a memory, call `remember()` directly.\n"
        )
        return body.encode("utf-8")

    def _entry_or_404(self, fname: str) -> dict:
        if not self.ready.wait(timeout=BOOTSTRAP_TIMEOUT):
            raise FuseOSError(errno.EAGAIN)
        with self._entries_lock:
            entry = self.entries.get(fname)
        if entry is None:
            raise FuseOSError(errno.ENOENT)
        return entry

    # ── FUSE ops ──

    def getattr(self, path: str, fh: int | None = None) -> dict:
        now = time.time()
        if path in ("/", "/memories"):
            return dict(
                st_mode=stat.S_IFDIR | 0o555,
                st_nlink=2,
                st_ctime=now,
                st_mtime=now,
                st_atime=now,
            )
        if path == "/README.md":
            body = self._readme_bytes()
            return dict(
                st_mode=stat.S_IFREG | 0o444,
                st_nlink=1,
                st_size=len(body),
                st_ctime=now,
                st_mtime=now,
                st_atime=now,
            )
        if path.startswith("/memories/"):
            fname = path[len("/memories/"):]
            entry = self._entry_or_404(fname)
            return dict(
                st_mode=stat.S_IFREG | 0o444,
                st_nlink=1,
                st_size=len(entry["bytes"]),
                st_ctime=now,
                st_mtime=now,
                st_atime=now,
            )
        raise FuseOSError(errno.ENOENT)

    def readdir(self, path: str, fh: int) -> list[str]:
        if path == "/":
            return [".", "..", "memories", "README.md"]
        if path == "/memories":
            if not self.ready.wait(timeout=BOOTSTRAP_TIMEOUT):
                raise FuseOSError(errno.EAGAIN)
            with self._entries_lock:
                names = sorted(self.entries.keys())
            return [".", "..", *names]
        raise FuseOSError(errno.ENOENT)

    def open(self, path: str, flags: int) -> int:
        # Read-only — refuse write/create flags.
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            raise FuseOSError(errno.EROFS)
        return 0

    def read(self, path: str, size: int, offset: int, fh: int) -> bytes:
        if path == "/README.md":
            body = self._readme_bytes()
        elif path.startswith("/memories/"):
            fname = path[len("/memories/"):]
            entry = self._entry_or_404(fname)
            body = entry["bytes"]
        else:
            raise FuseOSError(errno.ENOENT)
        return body[offset:offset + size]


def main() -> None:
    mount_point = sys.argv[1] if len(sys.argv) > 1 else "/mnt/muninn"
    os.makedirs(mount_point, exist_ok=True)
    # foreground=True keeps the python process alive as the FUSE server.
    # nothreads=False allows FUSE to dispatch multiple reads concurrently —
    # safe here because our state access is mutex-protected.
    FUSE(MemFs(), mount_point, foreground=True, nothreads=False, allow_other=False)


if __name__ == "__main__":
    main()
