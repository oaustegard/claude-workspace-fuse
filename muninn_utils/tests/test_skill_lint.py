"""Tests for muninn_utils.skill_lint.

validate_skill is a forcing function against the class of bug that shipped in the
verifying-claims skill (claude-skills #691): a colon-space inside an unquoted
`description` scalar makes the whole YAML frontmatter fail to parse, silently
dropping name/description (which drive skill triggering). These tests encode that
real failure so it cannot recur unnoticed.
"""
from __future__ import annotations

import pytest

from muninn_utils.skill_lint import validate_skill, validate_skill_file

GOOD = """---
name: verifying-claims
description: Check that a document's claims about code are true — pairs with TDD, not a gate.
metadata:
  version: 0.2.0
---
# verifying-claims
body text
"""

# The exact shape that shipped broken: colon-space in an unquoted description.
SHIPPED_BROKEN = (
    "---\n"
    "name: verifying-claims\n"
    "description: The agent reads the prose's meaning directly — no DSL to maintain. "
    "Pairs with TDD: the test suite is the gate, this skill is the review.\n"
    "---\n"
    "# verifying-claims\n"
)

# The fix that landed (#692): em-dash instead of colon-space.
SHIPPED_FIXED = SHIPPED_BROKEN.replace("Pairs with TDD:", "Pairs with TDD —")


def test_valid_frontmatter_returns_dict():
    fm = validate_skill(GOOD)
    assert fm["name"] == "verifying-claims"
    assert fm["description"].strip()


def test_shipped_broken_colon_space_raises():
    with pytest.raises(ValueError) as e:
        validate_skill(SHIPPED_BROKEN)
    assert "YAML" in str(e.value)


def test_shipped_fixed_passes():
    fm = validate_skill(SHIPPED_FIXED)
    assert fm["name"] == "verifying-claims"


def test_missing_name_raises():
    with pytest.raises(ValueError):
        validate_skill("---\ndescription: x\n---\nbody\n")


def test_empty_description_raises():
    with pytest.raises(ValueError):
        validate_skill('---\nname: a\ndescription: ""\n---\nbody\n')


def test_no_frontmatter_raises():
    with pytest.raises(ValueError):
        validate_skill("# just a heading\nno frontmatter here\n")


def test_no_closing_fence_raises():
    with pytest.raises(ValueError):
        validate_skill("---\nname: a\ndescription: b\n")


def test_require_version_enforced():
    no_version = "---\nname: a\ndescription: b\n---\nbody\n"
    validate_skill(no_version)  # ok without the flag
    with pytest.raises(ValueError):
        validate_skill(no_version, require_version=True)


def test_validate_skill_file(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(GOOD, encoding="utf-8")
    fm = validate_skill_file(str(p))
    assert fm["metadata"]["version"] == "0.2.0"
