"""
memory_to_okf — export a slice of Muninn memory as a conformant Open Knowledge
Format (OKF v0.1) bundle, and validate any bundle against the §9 conformance
contract.

OKF v0.1 spec: github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf

Why this exists: Muninn's memory schema already *is* OKF-shaped — type, tags,
timestamp, body, and refs-as-cross-links. This makes that latent format
explicit, producing a Turso-independent, agent-portable bundle another consumer
(a fresh boot, a CCotw session, yepgent) can read with nothing but `cat`.

Producer:  build_bundle(memories, out_dir, title=...)
Validator: validate_bundle(path) -> (ok: bool, issues: list[str])

The producer verifies its own output (gate-before-push): build_bundle runs the
validator and raises if the emitted bundle is non-conformant.

CLI:
    python3 memory_to_okf.py --tags small-reasoner-big-KB --out /tmp/bundle
    python3 memory_to_okf.py --validate /path/to/bundle
"""
from __future__ import annotations

import os
import re
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

import yaml

OKF_VERSION = "0.1"
RESERVED = {"index.md", "log.md"}

# ─────────────────────────────────────────────────────────────────────────────
# Memory → concept mapping
# ─────────────────────────────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.+?)\s*#*\s*$", re.M)
# refs are stored either as full uuids or 8-char prefixes (phase3-refs-discipline)
_REF_RE = re.compile(r"\b([0-9a-f]{8})\b")


def _id8(mem_id: str) -> str:
    return (mem_id or "").replace("-", "")[:8] or "unknown0"


def _slug_type(t: str) -> str:
    """Filesystem-safe directory name for a memory type."""
    s = re.sub(r"[^a-z0-9]+", "-", (t or "concept").lower()).strip("-")
    return s or "concept"


def _derive_title(body: str, fallback: str) -> str:
    """First markdown heading, else first non-empty line (trimmed), else id."""
    m = _HEADING_RE.search(body or "")
    if m:
        return m.group(1).strip()[:120]
    for line in (body or "").splitlines():
        line = line.strip()
        if line:
            return line[:120]
    return fallback


def _derive_description(body: str, title: str = "") -> str:
    """One-line summary: first prose sentence that isn't the title line itself.

    Memory bodies often lead with a title-as-first-line (no '#'), which would
    otherwise make description echo title. Skip that line, then take the next
    sentence-worth of prose.
    """
    text = _HEADING_RE.sub("", body or "").strip()
    # drop a leading line equal to (or starting with) the derived title
    if title:
        lines = text.splitlines()
        while lines and lines[0].strip() and (
            lines[0].strip()[:120] == title or lines[0].strip().startswith(title)
        ):
            lines.pop(0)
        text = "\n".join(lines).strip()
    text = re.sub(r"\s+", " ", text)
    if not text:
        return ""
    cut = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return cut[:200]


def _iso(ts) -> str | None:
    if not ts:
        return None
    return str(ts)


def memory_to_concept(mem: dict) -> dict:
    """Normalize a recall() row into an OKF concept descriptor (no I/O)."""
    mem_id = mem.get("id", "")
    body = mem.get("summary") or mem.get("body") or ""
    mem_type = (mem.get("type") or "concept").strip() or "concept"
    id8 = _id8(mem_id)
    path = f"{_slug_type(mem_type)}/{id8}.md"

    fm = {
        "type": mem_type,  # REQUIRED by OKF §4.1 / §9
        "title": _derive_title(body, id8),
    }
    desc = _derive_description(body, fm["title"])
    if desc:
        fm["description"] = desc
    tags = mem.get("tags") or []
    if tags:
        fm["tags"] = list(tags)
    ts = _iso(mem.get("created_at") or mem.get("t"))
    if ts:
        fm["timestamp"] = ts
    # extension keys (OKF §4.1 — consumers must tolerate/ preserve)
    fm["okf_memory_id"] = mem_id
    if mem.get("priority"):
        fm["okf_priority"] = mem["priority"]
    if mem.get("confidence") is not None:
        fm["okf_confidence"] = mem["confidence"]

    # outbound refs (8-char prefixes) for later cross-link resolution
    raw_refs = mem.get("refs") or []
    ref8 = []
    for r in raw_refs:
        ref8.append(_id8(r) if "-" in str(r) or len(str(r)) > 8 else str(r))
    # also mine the body for inline 8-char id mentions
    body_refs = set(_REF_RE.findall(body))

    return {
        "path": path,
        "id8": id8,
        "frontmatter": fm,
        "body": body,
        "type": mem_type,
        "title": fm["title"],
        "description": desc,
        "timestamp": ts,
        "refs": ref8,
        "body_refs": body_refs,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Bundle assembly
# ─────────────────────────────────────────────────────────────────────────────

def _emit_frontmatter(fm: dict) -> str:
    y = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{y}---\n"


def _related_section(concept: dict, id8_to_path: dict) -> str:
    """Render resolvable refs as a bundle-relative '# Related' cross-link block."""
    targets = []
    seen = set()
    for r in list(concept["refs"]) + sorted(concept["body_refs"]):
        if r == concept["id8"] or r in seen:
            continue
        if r in id8_to_path:
            seen.add(r)
            targets.append(r)
    if not targets:
        return ""
    lines = ["", "# Related", ""]
    for r in targets:
        path, title = id8_to_path[r]
        lines.append(f"* [{title}](/{path})")
    return "\n".join(lines) + "\n"


def build_bundle(memories: list[dict], out_dir: str, title: str = "Muninn Knowledge Bundle",
                 description: str = "") -> dict:
    """Write a conformant OKF bundle from recall() rows. Returns a manifest dict.

    Self-verifying: runs validate_bundle on the result and raises on failure.
    """
    out = Path(out_dir)
    if out.exists():
        # clean slate to avoid stale concepts
        for p in sorted(out.rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()
    out.mkdir(parents=True, exist_ok=True)

    concepts = [memory_to_concept(m) for m in memories]
    # de-dup by id8 (recall can return overlaps across tag queries)
    uniq = {}
    for c in concepts:
        uniq.setdefault(c["id8"], c)
    concepts = list(uniq.values())

    id8_to_path = {c["id8"]: (c["path"], c["title"]) for c in concepts}

    # write concept files
    for c in concepts:
        fpath = out / c["path"]
        fpath.parent.mkdir(parents=True, exist_ok=True)
        text = _emit_frontmatter(c["frontmatter"]) + "\n" + c["body"].rstrip() + "\n"
        text += _related_section(c, id8_to_path)
        fpath.write_text(text, encoding="utf-8")

    # group by type-dir for index generation
    by_dir: dict[str, list[dict]] = {}
    for c in concepts:
        d = str(Path(c["path"]).parent)
        by_dir.setdefault(d, []).append(c)

    # per-directory index.md (no frontmatter — §6)
    for d, items in by_dir.items():
        lines = [f"# {d}", ""]
        for c in sorted(items, key=lambda x: x["title"].lower()):
            fname = Path(c["path"]).name
            desc = f" - {c['description']}" if c["description"] else ""
            lines.append(f"* [{c['title']}]({fname}){desc}")
        (out / d / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # root index.md (the ONE place frontmatter is allowed in an index — §11)
    root_fm = {"okf_version": OKF_VERSION, "title": title}
    if description:
        root_fm["description"] = description
    root_lines = [_emit_frontmatter(root_fm), f"# {title}", ""]
    if description:
        root_lines.append(description + "\n")
    for d in sorted(by_dir):
        items = by_dir[d]
        root_lines.append(f"# {d}  ({len(items)})")
        root_lines.append("")
        for c in sorted(items, key=lambda x: x["title"].lower()):
            desc = f" - {c['description']}" if c["description"] else ""
            root_lines.append(f"* [{c['title']}](/{c['path']}){desc}")
        root_lines.append("")
    (out / "index.md").write_text("\n".join(root_lines), encoding="utf-8")

    # root log.md — group by creation date, newest first (§7)
    by_date: dict[str, list[dict]] = {}
    for c in concepts:
        day = (c["timestamp"] or "")[:10] or "unknown"
        by_date.setdefault(day, []).append(c)
    log_lines = ["# Bundle Update Log", ""]
    for day in sorted((d for d in by_date if d != "unknown"), reverse=True):
        log_lines.append(f"## {day}")
        for c in by_date[day]:
            log_lines.append(f"* **Creation**: [{c['title']}](/{c['path']})")
        log_lines.append("")
    (out / "log.md").write_text("\n".join(log_lines), encoding="utf-8")

    manifest = {
        "title": title,
        "okf_version": OKF_VERSION,
        "concept_count": len(concepts),
        "types": sorted({c["type"] for c in concepts}),
        "out_dir": str(out),
    }

    ok, issues = validate_bundle(str(out))
    manifest["conformant"] = ok
    manifest["validation_issues"] = issues
    if not ok:
        raise ValueError(f"Produced a non-conformant bundle: {issues}")
    return manifest


# ─────────────────────────────────────────────────────────────────────────────
# Validator — OKF v0.1 §9 conformance
# ─────────────────────────────────────────────────────────────────────────────

_DATE_HEADING_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$")


def _split_frontmatter(text: str):
    """Return (frontmatter_dict_or_None, parse_error_or_None)."""
    if not text.startswith("---"):
        return None, "no frontmatter block"
    parts = text.split("\n", 1)
    rest = parts[1] if len(parts) > 1 else ""
    m = re.search(r"\n---\s*(\n|$)", rest)
    if not m:
        return None, "unterminated frontmatter block"
    block = rest[:m.start()]
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as e:
        return None, f"unparseable YAML: {e}"
    if not isinstance(data, dict):
        return None, "frontmatter is not a mapping"
    return data, None


def validate_bundle(path: str) -> tuple[bool, list[str]]:
    """Check a directory tree against OKF v0.1 §9. Returns (ok, issues)."""
    root = Path(path)
    issues: list[str] = []
    if not root.is_dir():
        return False, [f"{path}: not a directory"]

    md_files = sorted(root.rglob("*.md"))
    if not md_files:
        issues.append("bundle contains no markdown files")

    for f in md_files:
        rel = f.relative_to(root).as_posix()
        name = f.name
        text = f.read_text(encoding="utf-8")

        if name == "index.md":
            # §6: no frontmatter, EXCEPT root index.md may carry okf_version (§11)
            if text.startswith("---"):
                fm, err = _split_frontmatter(text)
                is_root = f.parent == root
                if not is_root:
                    issues.append(f"{rel}: non-root index.md must not have frontmatter (§6)")
                elif err:
                    issues.append(f"{rel}: root index frontmatter {err}")
            continue

        if name == "log.md":
            # §7: date headings must be ISO YYYY-MM-DD
            for ln in text.splitlines():
                if ln.startswith("## "):
                    if not _DATE_HEADING_RE.match(ln):
                        issues.append(f"{rel}: log date heading not ISO YYYY-MM-DD: {ln!r}")
            continue

        # concept document — §9.1 + §9.2
        fm, err = _split_frontmatter(text)
        if err:
            issues.append(f"{rel}: {err}")
            continue
        t = fm.get("type")
        if not (isinstance(t, str) and t.strip()):
            issues.append(f"{rel}: missing/empty required 'type' field (§9.2)")

    return (len(issues) == 0), issues


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _load_memories(tags, query, n, exclude_confidential=True):
    from scripts import recall
    rows = []
    if tags:
        for t in tags:
            rows.extend(recall(tags=[t], n=n))
    if query:
        rows.extend(recall(query=query, n=n))
    # de-dup by id; drop confidential (private-tag-discipline)
    seen, out = set(), []
    for r in rows:
        rid = r.get("id")
        if rid in seen:
            continue
        seen.add(rid)
        if exclude_confidential and "confidential" in (r.get("tags") or []):
            continue
        out.append(r)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Muninn memory → OKF v0.1 producer/validator")
    ap.add_argument("--tags", nargs="*", help="recall by these tags (OR)")
    ap.add_argument("--query", help="recall by FTS query")
    ap.add_argument("--n", type=int, default=50, help="max rows per tag/query")
    ap.add_argument("--out", default="/tmp/okf-bundle", help="output bundle dir")
    ap.add_argument("--title", default="Muninn Knowledge Bundle")
    ap.add_argument("--validate", metavar="PATH", help="validate an existing bundle and exit")
    args = ap.parse_args(argv)

    if args.validate:
        ok, issues = validate_bundle(args.validate)
        print(("CONFORMANT" if ok else "NON-CONFORMANT") + f": {args.validate}")
        for i in issues:
            print("  -", i)
        sys.exit(0 if ok else 1)

    mems = _load_memories(args.tags, args.query, args.n)
    if not mems:
        print("no memories matched", file=sys.stderr)
        sys.exit(2)
    manifest = build_bundle(mems, args.out, title=args.title)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
