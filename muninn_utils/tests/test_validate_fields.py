"""validate_fields invariants, plus the drift guard on the vendored vocabulary.

No network. The drift test reads remembering/scripts/result.py from the repo
checkout, so it fails in CI the moment the vendored copy falls behind.
"""
import sys
from pathlib import Path

import pytest

from muninn_utils import validate_fields as vf
from muninn_utils.validate_fields import (
    ALIASES,
    VALID_FIELDS,
    RecallFieldError,
    canonical,
    validate_recall_fields,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_canonical_passes_through_and_resolves():
    assert canonical("summary") == "summary"
    assert canonical("content") == "summary"
    assert canonical("limit") is None


def test_valid_fields_pass_and_return_in_order():
    assert validate_recall_fields("summary", "id", "created_at") == (
        "summary", "id", "created_at",
    )


def test_the_failure_this_module_exists_for():
    # `content` is the mistake that cost a session: plain-dict .get('content','')
    # returns '' forever instead of raising.
    with pytest.raises(RecallFieldError) as e:
        validate_recall_fields("content")
    assert "summary" in str(e.value)


def test_alias_raises_by_default_and_resolves_when_allowed():
    with pytest.raises(RecallFieldError):
        validate_recall_fields("text")
    assert validate_recall_fields("text", allow_aliases=True) == ("summary",)


def test_all_bad_names_reported_in_one_error():
    with pytest.raises(RecallFieldError) as e:
        validate_recall_fields("content", "body", "wombat")
    msg = str(e.value)
    for bad in ("content", "body", "wombat"):
        assert bad in msg


def test_error_names_the_to_dict_bypass():
    with pytest.raises(RecallFieldError) as e:
        validate_recall_fields("content")
    assert "to_dict()" in str(e.value)


def test_non_string_and_empty_are_rejected():
    with pytest.raises(RecallFieldError):
        validate_recall_fields()
    with pytest.raises(RecallFieldError):
        validate_recall_fields(None)  # type: ignore[arg-type]


def test_every_alias_target_is_a_valid_field():
    assert not {v for v in ALIASES.values() if v not in VALID_FIELDS}


def test_vendored_vocabulary_matches_result_py():
    """Drift guard: the vendored fallback must equal the source of truth."""
    remembering = REPO_ROOT / "remembering"
    if not (remembering / "scripts" / "result.py").exists():
        pytest.skip("remembering/ not present in this checkout")

    sys.path.insert(0, str(remembering))
    try:
        from scripts.result import COMMON_MISTAKES
        from scripts.result import VALID_FIELDS as LIVE_FIELDS
    finally:
        sys.path.remove(str(remembering))

    assert vf._VENDORED_VALID_FIELDS == set(LIVE_FIELDS), (
        "vendored VALID_FIELDS drifted from remembering/scripts/result.py"
    )
    assert vf._VENDORED_ALIASES == dict(COMMON_MISTAKES), (
        "vendored ALIASES drifted from remembering/scripts/result.py"
    )


def test_short_names_do_not_match_half_the_vocabulary():
    """A substring test made 'n' suggest access_count, alternatives, ... ."""
    with pytest.raises(RecallFieldError) as e:
        validate_recall_fields("n")
    assert "access_count" not in str(e.value).split("Valid fields:")[0]
