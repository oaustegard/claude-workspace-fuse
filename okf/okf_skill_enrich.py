"""
okf_skill_enrich — add OKF concept metadata to a SKILL.md WITHOUT breaking the
skill frontmatter schema.

The skill validator (skill-creator/scripts/quick_validate.py) enforces a strict
top-level allowlist:
    {name, description, license, allowed-tools, metadata, compatibility}
Any other top-level key fails upload. It does NOT police nested keys under
`metadata`. Therefore OKF fields go under `metadata.okf`, and `name` /
`description` / other top-level keys are never modified.

This is non-breaking and idempotent: re-running updates metadata.okf in place
without disturbing anything else. `name` and `description` are treated as
immutable (they carry hard constraints and are written for skill triggering).

A generic OKF consumer expects top-level `type`; it won't read metadata.okf
directly. Consumption-side, hoist metadata.okf -> top-level when emitting a
derived OKF bundle (see hoist_to_okf). The SKILL.md stays the skill-valid
source; the bundle is regenerable.

    enrich_skill_md(path, type='Skill', tags=None, write=False) -> str
    hoist_to_okf(skill_fm) -> dict   # metadata.okf -> flat OKF frontmatter
"""
from __future__ import annotations
import re, subprocess
from pathlib import Path
import yaml

SKILL_ALLOWED_TOP = {"name", "description", "license", "allowed-tools",
                     "metadata", "compatibility"}
_HEADING_RE = re.compile(r"^\s*#\s+(.+?)\s*#*\s*$", re.M)


def _split(content: str):
    """Return (frontmatter_dict, body_str, raw_fm_text) or raise."""
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", content, re.DOTALL)
    if not m:
        raise ValueError("no parseable frontmatter")
    fm = yaml.safe_load(m.group(1))
    if not isinstance(fm, dict):
        raise ValueError("frontmatter is not a mapping")
    return fm, m.group(2), m.group(1)


def _git_timestamp(path: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(path.parent), "log", "-1", "--format=%cI", "--", path.name],
            capture_output=True, text=True, timeout=10)
        ts = out.stdout.strip()
        return ts or None
    except Exception:
        return None


def _derive_title(body: str, name: str) -> str:
    m = _HEADING_RE.search(body or "")
    if m:
        return m.group(1).strip()[:120]
    # humanize the kebab name as a fallback
    return name.replace("-", " ").title()


def enrich_skill_md(path, type: str = "Skill", tags=None, write: bool = False) -> str:
    """Inject metadata.okf into a SKILL.md. Returns the new file text.

    Never alters name/description or any top-level key except by adding the
    OKF block strictly under metadata.okf. Idempotent.
    """
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    fm, body, _ = _split(content)

    # hard rule: do not touch name/description
    name = (fm.get("name") or path.parent.name).strip()

    meta = fm.get("metadata")
    if not isinstance(meta, dict):
        meta = {} if meta is None else {"_prev": str(meta)}

    # OKF data MUST be flat string->string under metadata: the official
    # skills-ref parser coerces metadata via {str(k): str(v)}, which mangles
    # nested dicts/lists into Python-repr strings. Namespace with an 'okf.'
    # prefix (spec advises unique key names to avoid conflicts); join tags.
    okf = {
        "okf.type": str(type),
        "okf.title": meta.get("okf.title") or _derive_title(body, name),
    }
    if fm.get("description"):
        okf["okf.description"] = str(fm["description"]).split(". ")[0][:200]
    ts = _git_timestamp(path)
    if ts:
        okf["okf.timestamp"] = ts
    prev_tags = [t for t in str(meta.get("okf.tags", "")).split(",") if t]
    merged_tags = sorted(set(prev_tags) | set(tags or []))
    if merged_tags:
        okf["okf.tags"] = ",".join(merged_tags)

    # drop any earlier nested form, write flat keys
    meta.pop("okf", None)
    for k in [k for k in meta if k.startswith("okf.")]:
        meta.pop(k)
    meta.update(okf)
    fm["metadata"] = meta

    # re-emit with name/description first for readability; preserve all keys
    ordered = {}
    for k in ("name", "description", "license", "allowed-tools", "compatibility", "metadata"):
        if k in fm:
            ordered[k] = fm[k]
    for k in fm:  # any other (shouldn't exist, but never drop)
        ordered.setdefault(k, fm[k])

    new_fm = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True, width=1000)
    new_text = f"---\n{new_fm}---\n{body}"
    if write:
        path.write_text(new_text, encoding="utf-8")
    return new_text


def hoist_to_okf(skill_fm: dict) -> dict:
    """Consumption-side: lift flat metadata 'okf.*' keys -> top-level OKF
    frontmatter for a derived bundle. The skill source is unchanged."""
    meta = skill_fm.get("metadata") or {}
    g = lambda k: meta.get(f"okf.{k}")
    out = {"type": g("type") or "Skill"}
    if g("title"):
        out["title"] = g("title")
    desc = g("description") or skill_fm.get("description")
    if desc:
        out["description"] = str(desc)[:200]
    if g("tags"):
        out["tags"] = [t for t in str(g("tags")).split(",") if t]
    if g("timestamp"):
        out["timestamp"] = g("timestamp")
    if skill_fm.get("name"):
        out["okf_skill_name"] = skill_fm["name"]
    return out
