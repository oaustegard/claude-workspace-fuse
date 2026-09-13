"""Snapshot builder: package Muninn for use in another Claude.ai project.

Entry point:
    from snapshot import build_snapshot
    result = build_snapshot(out_dir="/path/to/output")

See README.md for design notes.
"""

from .build import build_snapshot

__all__ = ["build_snapshot"]
