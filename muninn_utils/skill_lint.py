"""validate_skill — parse and sanity-check a SKILL.md's YAML frontmatter.

A forcing function for the class of bug that shipped in the verifying-claims
skill (claude-skills #691): a colon-space inside an unquoted `description` scalar
makes the whole frontmatter fail to parse, which silently drops name/description
— the fields that drive skill triggering. Run this before pushing any SKILL.md
the way blog posts run validate_blog_html; the check then doesn't depend on
anyone remembering to eyeball the YAML.
"""
from __future__ import annotations

import yaml


def _frontmatter_block(text: str) -> str:
    """Return the raw YAML between the leading '---' fences, or raise."""
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        raise ValueError("no YAML frontmatter (file must start with '---')")
    parts = stripped.split("---", 2)
    # parts[0] == '' (before first fence); parts[1] == frontmatter; parts[2] == body
    if len(parts) < 3:
        raise ValueError("no closing '---' fence for the frontmatter")
    return parts[1]


def validate_skill(text: str, *, require_version: bool = False) -> dict:
    """Validate SKILL.md frontmatter. Returns the parsed mapping, or raises
    ValueError with a readable reason. Pass the file's full text."""
    fm_text = _frontmatter_block(text)
    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError as e:
        first = str(e).splitlines()[0]
        raise ValueError(f"invalid YAML frontmatter: {first}") from e
    if not isinstance(fm, dict):
        raise ValueError("frontmatter is not a mapping")
    for key in ("name", "description"):
        val = fm.get(key)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"frontmatter '{key}' must be a non-empty string")
    if require_version:
        version = (fm.get("metadata") or {}).get("version")
        if not version:
            raise ValueError("frontmatter 'metadata.version' is required")
    return fm


def validate_skill_file(path: str, *, require_version: bool = False) -> dict:
    """validate_skill for a file on disk."""
    with open(path, encoding="utf-8") as f:
        return validate_skill(f.read(), require_version=require_version)
