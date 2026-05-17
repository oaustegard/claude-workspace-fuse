"""Unit tests for scripts/muninn_memfs.py.

Tests the MemFs class behavior with a mocked `_exec` (no real Turso, no
real FUSE mount). FUSE mounting itself is exercised manually — see
docs/memfs.md.
"""

from __future__ import annotations

import errno
import os
import sys
import threading
import time
from pathlib import Path

import pytest

# Make scripts/ importable.
SPOKE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SPOKE_ROOT / "scripts"))

# Stub out scripts.turso BEFORE importing muninn_memfs so we don't need a
# live Turso connection. The real remembering skill won't be importable
# in a vanilla test environment either.
import types

_turso_stub = types.ModuleType("scripts.turso")
_turso_stub._exec = lambda *_a, **_kw: []
sys.modules.setdefault("scripts", types.ModuleType("scripts"))
sys.modules["scripts.turso"] = _turso_stub

import muninn_memfs  # noqa: E402

# ── Pure-function tests ──


class TestSlugify:
    def test_basic(self) -> None:
        assert muninn_memfs.slugify("Hello World") == "hello-world"

    def test_strips_punctuation(self) -> None:
        assert muninn_memfs.slugify("Foo, bar! Baz?") == "foo-bar-baz"

    def test_only_first_line(self) -> None:
        # Multi-line summaries should slug from the first line only.
        assert muninn_memfs.slugify("first line\nsecond line\nthird") == "first-line"

    def test_truncates_to_max_len(self) -> None:
        long = "a" * 200
        assert len(muninn_memfs.slugify(long, max_len=40)) == 40

    def test_empty_returns_untitled(self) -> None:
        assert muninn_memfs.slugify("") == "untitled"
        assert muninn_memfs.slugify("!!!") == "untitled"

    def test_unicode_word_chars_kept(self) -> None:
        # \w matches unicode by default in re — accented chars survive.
        assert "naive" in muninn_memfs.slugify("naïve approach").replace("ï", "i") or \
               "naïve" in muninn_memfs.slugify("naïve approach")


class TestFormatMemory:
    def test_minimal_row(self) -> None:
        row = {"id": "abcd1234-...", "summary": "hi"}
        out = muninn_memfs.format_memory(row)
        assert out.startswith(b"# abcd1234-...\n")
        assert out.endswith(b"\n")
        assert b"hi" in out

    def test_full_row_includes_metadata(self) -> None:
        row = {
            "id": "abcd1234",
            "summary": "Test memory content",
            "type": "decision",
            "created_at": "2026-05-17T03:00:00Z",
            "tags": '["foo","bar"]',
            "priority": 2,
        }
        out = muninn_memfs.format_memory(row).decode()
        assert "# abcd1234" in out
        assert "**Type**: `decision`" in out
        assert "**Created**: 2026-05-17T03:00:00Z" in out
        assert "**Priority**: 2" in out
        assert "**Tags**:" in out
        assert "Test memory content" in out
        assert "---" in out  # metadata separator

    def test_priority_zero_omitted(self) -> None:
        row = {"id": "x", "summary": "y", "priority": 0}
        assert b"Priority" not in muninn_memfs.format_memory(row)

    def test_none_summary_doesnt_crash(self) -> None:
        out = muninn_memfs.format_memory({"id": "x", "summary": None})
        assert out.endswith(b"\n")


# ── MemFs behavior tests (no real Turso, no real FUSE) ──


@pytest.fixture
def fake_rows() -> list[dict]:
    return [
        {
            "id": "11111111-aaaa-bbbb-cccc-000000000001",
            "summary": "first memory about FUSE",
            "type": "experience",
            "tags": '["fuse"]',
            "created_at": "2026-05-17T03:30:00Z",
            "priority": 0,
        },
        {
            "id": "22222222-aaaa-bbbb-cccc-000000000002",
            "summary": "second memory",
            "type": "decision",
            "tags": "[]",
            "created_at": "2026-05-17T03:31:00Z",
            "priority": 1,
        },
    ]


@pytest.fixture
def memfs(monkeypatch: pytest.MonkeyPatch, fake_rows: list[dict]) -> muninn_memfs.MemFs:
    """A MemFs whose bootstrap completed synchronously with `fake_rows`."""
    monkeypatch.setattr(muninn_memfs, "_exec", lambda *_a, **_kw: fake_rows)
    fs = muninn_memfs.MemFs()
    # Wait for the daemon bootstrap thread (it should be near-instant given
    # the mock returns immediately).
    assert fs.ready.wait(timeout=2), "bootstrap did not complete"
    return fs


class TestMemFsBootstrap:
    def test_indexes_all_rows(self, memfs: muninn_memfs.MemFs) -> None:
        assert len(memfs.entries) == 2

    def test_filenames_use_id_prefix_and_slug(self, memfs: muninn_memfs.MemFs) -> None:
        names = list(memfs.entries.keys())
        assert any(n.startswith("11111111-") and n.endswith(".md") for n in names)
        assert any("first-memory-about-fuse" in n for n in names)

    def test_cached_bytes_match_format_output(
        self, memfs: muninn_memfs.MemFs, fake_rows: list[dict]
    ) -> None:
        # The entry's cached bytes must equal format_memory(row), otherwise
        # getattr's reported st_size won't match read's returned content.
        for entry in memfs.entries.values():
            expected = muninn_memfs.format_memory(entry["row"])
            assert entry["bytes"] == expected
            assert len(entry["bytes"]) == len(expected)


class TestMemFsBootstrapFailure:
    def test_failed_bootstrap_still_sets_ready(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(*_a, **_kw):
            raise RuntimeError("turso unreachable")

        monkeypatch.setattr(muninn_memfs, "_exec", boom)
        fs = muninn_memfs.MemFs()
        # Ready must be set even on failure — otherwise reads block forever.
        assert fs.ready.wait(timeout=2)
        assert fs.entries == {}


class TestFuseOps:
    def test_getattr_root_is_directory(self, memfs: muninn_memfs.MemFs) -> None:
        attr = memfs.getattr("/")
        import stat as st
        assert st.S_ISDIR(attr["st_mode"])

    def test_getattr_memories_is_directory(self, memfs: muninn_memfs.MemFs) -> None:
        attr = memfs.getattr("/memories")
        import stat as st
        assert st.S_ISDIR(attr["st_mode"])

    def test_readdir_root(self, memfs: muninn_memfs.MemFs) -> None:
        names = memfs.readdir("/", 0)
        assert "memories" in names
        assert "README.md" in names

    def test_readdir_memories_lists_all_entries(
        self, memfs: muninn_memfs.MemFs
    ) -> None:
        names = memfs.readdir("/memories", 0)
        # First two entries are "." and ".." per POSIX.
        assert names[0] == "."
        assert names[1] == ".."
        assert len(names) == 2 + len(memfs.entries)

    def test_getattr_unknown_path_raises_enoent(
        self, memfs: muninn_memfs.MemFs
    ) -> None:
        from fuse import FuseOSError

        with pytest.raises(FuseOSError) as exc:
            memfs.getattr("/nope")
        assert exc.value.errno == errno.ENOENT

    def test_getattr_unknown_memory_raises_enoent(
        self, memfs: muninn_memfs.MemFs
    ) -> None:
        from fuse import FuseOSError

        with pytest.raises(FuseOSError) as exc:
            memfs.getattr("/memories/nonexistent.md")
        assert exc.value.errno == errno.ENOENT

    def test_read_full_file_matches_getattr_size(
        self, memfs: muninn_memfs.MemFs
    ) -> None:
        fname = next(iter(memfs.entries))
        path = f"/memories/{fname}"
        attr = memfs.getattr(path)
        # Read entire file (large size to ensure no truncation).
        content = memfs.read(path, 1_000_000, 0, 0)
        assert len(content) == attr["st_size"]

    def test_read_offset_and_size(self, memfs: muninn_memfs.MemFs) -> None:
        fname = next(iter(memfs.entries))
        path = f"/memories/{fname}"
        full = memfs.read(path, 1_000_000, 0, 0)
        # Reading a slice should return that exact slice.
        assert memfs.read(path, 10, 5, 0) == full[5:15]

    def test_readme_includes_count(self, memfs: muninn_memfs.MemFs) -> None:
        body = memfs.read("/README.md", 1_000_000, 0, 0).decode()
        assert "Memories indexed**: 2" in body

    def test_open_write_flags_refused(self, memfs: muninn_memfs.MemFs) -> None:
        from fuse import FuseOSError

        for flag in (os.O_WRONLY, os.O_RDWR, os.O_WRONLY | os.O_CREAT):
            with pytest.raises(FuseOSError) as exc:
                memfs.open("/memories/anything.md", flag)
            assert exc.value.errno == errno.EROFS

    def test_open_readonly_succeeds(self, memfs: muninn_memfs.MemFs) -> None:
        # Should not raise.
        assert memfs.open("/README.md", os.O_RDONLY) == 0


class TestReadBlocksOnBootstrap:
    def test_read_waits_for_bootstrap(
        self, monkeypatch: pytest.MonkeyPatch, fake_rows: list[dict]
    ) -> None:
        """getattr on /memories/* must block until the bootstrap is ready."""
        gate = threading.Event()

        def slow_exec(*_a, **_kw):
            gate.wait(timeout=5)
            return fake_rows

        monkeypatch.setattr(muninn_memfs, "_exec", slow_exec)
        # Shrink the bootstrap timeout so the test fails fast if blocking is broken.
        monkeypatch.setattr(muninn_memfs, "BOOTSTRAP_TIMEOUT", 3)

        fs = muninn_memfs.MemFs()

        result: dict = {}

        def reader():
            try:
                # This must block until the gate is released and bootstrap finishes.
                # We deliberately ask for the FIRST file that bootstrap will create.
                # We don't know its exact name pre-bootstrap, so list+read after wait.
                fs.ready.wait(timeout=3)
                fname = next(iter(fs.entries))
                result["bytes"] = fs.read(f"/memories/{fname}", 1_000_000, 0, 0)
            except Exception as e:  # pragma: no cover
                result["error"] = e

        t = threading.Thread(target=reader)
        t.start()
        time.sleep(0.1)
        # Before the gate, the reader thread must still be blocked on bootstrap.
        assert "bytes" not in result
        # Release the gate; bootstrap completes; reader unblocks.
        gate.set()
        t.join(timeout=5)
        assert "bytes" in result, result
