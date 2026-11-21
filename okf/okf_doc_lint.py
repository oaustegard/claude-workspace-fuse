"""
okf_doc_lint — read-only audit of OKF-style frontmatter coverage across an
arbitrary markdown documentation tree (READMEs, CLAUDE.md, SKILL.md, guides).

This is NOT an OKF bundle conformance check (see memory_to_okf.validate_bundle
for that). Docs are not a knowledge bundle; this borrows OKF's frontmatter
*vocabulary* — title / description / tags / timestamp, plus an optional type —
and reports which docs would benefit from it. Nothing is mutated.

OKF reserves index.md / log.md and treats them specially; README.md is NOT
reserved (it's a concept doc in OKF terms). Both facts are surfaced, not enforced.

Usage:
    python3 okf_doc_lint.py PATH [PATH ...]
    python3 okf_doc_lint.py /repo --glob '**/*.md'
"""
from __future__ import annotations
import re, sys, glob, argparse
from pathlib import Path
import yaml

RECOMMENDED = ["type", "title", "description", "tags", "timestamp"]
RESERVED = {"index.md", "log.md"}


def split_frontmatter(text: str):
    if not text.startswith("---"):
        return None
    rest = text.split("\n", 1)[1] if "\n" in text else ""
    m = re.search(r"\n---\s*(\n|$)", rest)
    if not m:
        return None
    try:
        data = yaml.safe_load(rest[:m.start()])
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def audit(files: list[Path], root: Path):
    rows, have = [], {k: 0 for k in RECOMMENDED}
    for f in sorted(files):
        rel = f.relative_to(root).as_posix() if root in f.parents or f == root else f.name
        name = f.name
        fm = split_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        present = {k: (fm.get(k) not in (None, "", []) if fm else False) for k in RECOMMENDED}
        for k, v in present.items():
            have[k] += int(v)
        note = ""
        if name in RESERVED:
            note = "OKF-reserved (no frontmatter expected)"
        elif name.lower().startswith("readme"):
            note = "repo index by convention; OKF would type it as a concept"
        rows.append((rel, fm is not None, present, note))
    return rows, have


def main(argv=None):
    ap = argparse.ArgumentParser(description="OKF-frontmatter coverage linter (read-only)")
    ap.add_argument("paths", nargs="+", help="files or directories")
    ap.add_argument("--glob", default="**/*.md", help="glob for directories (default **/*.md)")
    args = ap.parse_args(argv)

    files, root = [], Path(".").resolve()
    for p in args.paths:
        pp = Path(p)
        if pp.is_dir():
            files += [Path(x) for x in glob.glob(str(pp / args.glob), recursive=True)]
            root = pp.resolve()
        elif pp.is_file():
            files.append(pp)
    files = [f for f in files if f.is_file()]
    if not files:
        print("no markdown files found", file=sys.stderr); sys.exit(2)

    rows, have = audit(files, root)
    tick = lambda b: "✓" if b else "·"
    w = min(60, max(len(r[0]) for r in rows))
    print(f"{'file':<{w}}  fm  " + " ".join(f"{k[:4]:>4}" for k in RECOMMENDED) + "  note")
    print("-" * (w + 6 + 5 * len(RECOMMENDED) + 6))
    for rel, has_fm, present, note in rows:
        cells = " ".join(f"{tick(present[k]):>4}" for k in RECOMMENDED)
        print(f"{rel[:w]:<{w}}  {tick(has_fm)}   {cells}  {note}")

    n = len(rows)
    print(f"\n{n} docs. recommended-field coverage:")
    for k in RECOMMENDED:
        print(f"  {k:<12} {have[k]:>3}/{n}  ({100*have[k]//n}%)")


if __name__ == "__main__":
    main()
