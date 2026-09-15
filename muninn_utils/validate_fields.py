"""validate_fields — authoring-time guard on recall() field names.

Ops entry ``remembering-api`` has prescribed this import as its FORCING FUNCTION
since well before the module existed::

    from muninn_utils.validate_fields import validate_recall_fields
    validate_recall_fields('summary', 'valid_from', 'id')

It raised ``ModuleNotFoundError``. Shipping it.

WHY IT IS NEEDED AT ALL, given that ``MemoryResult`` already validates:
``MemoryResult`` guards ``m.summary``, ``m['summary']`` and ``m.get('summary')``,
resolving known aliases with a ``DeprecationWarning``. But ``to_dict()`` and
``copy()`` return a **plain dict**, and every guarantee ends there — a plain
``d.get('content', '')`` returns ``''`` forever, silently, and reads at the call
site as "recall found nothing". That is the failure this module exists to catch:
not a wrong field on a guarded object, but a right-looking field on an unguarded
one. Call it once before the loop, and the wrong name dies at authoring time
instead of surfacing as empty output.

The field vocabulary is owned by ``remembering/scripts/result.py``. This module
imports it when importable and falls back to a vendored copy otherwise;
``tests/test_validate_fields.py`` fails if the two drift apart.
"""

import difflib

__all__ = [
    "ALIASES",
    "VALID_FIELDS",
    "RecallFieldError",
    "canonical",
    "validate_recall_fields",
]

# Vendored fallback, kept honest by the drift test. Source of truth is
# remembering/scripts/result.py.
_VENDORED_VALID_FIELDS: set[str] = {
    "id", "type", "t",
    "summary", "summary_preview", "confidence", "tags", "refs", "priority",
    "session_id",
    "created_at", "updated_at", "valid_from",
    "access_count", "last_accessed",
    "bm25_score", "composite_rank", "composite_score",
    "alternatives",
    "has_full", "deleted_at",
    "relative_age",
}

_VENDORED_ALIASES: dict[str, str] = {
    "content": "summary", "text": "summary", "body": "summary",
    "message": "summary", "value": "summary", "memory": "summary",
    "what": "summary",
    "conf": "confidence", "score": "confidence",
    "timestamp": "t", "time": "t", "datetime": "t", "date": "t",
    "created": "created_at", "updated": "updated_at",
    "tag": "tags", "ref": "refs", "references": "refs",
    "prio": "priority", "importance": "priority",
    "session": "session_id",
    "accesses": "access_count", "access": "access_count",
    "last_access": "last_accessed",
}


def _load_vocabulary() -> tuple[set[str], dict[str, str]]:
    """Prefer the live vocabulary; fall back to the vendored copy.

    ``scripts`` is importable once muninn-boot has written the ``.pth``. In a
    bare checkout or a fresh CI runner it is not, and the vendored copy keeps
    this module usable rather than making the guard itself the thing that
    breaks.
    """
    try:
        from scripts.result import COMMON_MISTAKES, VALID_FIELDS  # type: ignore
        return set(VALID_FIELDS), dict(COMMON_MISTAKES)
    except Exception:  # noqa: BLE001 - a guard that itself explodes is worse than a stale one
        return set(_VENDORED_VALID_FIELDS), dict(_VENDORED_ALIASES)


VALID_FIELDS, ALIASES = _load_vocabulary()


class RecallFieldError(ValueError):
    """Raised for a field name recall() results do not carry."""


def canonical(field: str) -> str | None:
    """Canonical name for ``field``, or None if it is not a recall field.

    Returns ``field`` unchanged when already canonical, and resolves a known
    alias (``'content'`` -> ``'summary'``).
    """
    if field in VALID_FIELDS:
        return field
    return ALIASES.get(field)


def _suggest(field: str) -> str:
    hit = ALIASES.get(field)
    if hit:
        return f"  {field!r} -> did you mean {hit!r}?"
    # difflib, not substring: a substring test lets a one-character name match
    # half the vocabulary ('n' is in 'access_count') and buries the real answer.
    near = difflib.get_close_matches(field.lower(), sorted(VALID_FIELDS), n=3, cutoff=0.6)
    if near:
        return f"  {field!r} -> not a recall field; close: {', '.join(near)}"
    return f"  {field!r} -> not a recall field"


def validate_recall_fields(*fields: str, allow_aliases: bool = False) -> tuple[str, ...]:
    """Assert every name in ``fields`` is a real recall() field.

    Call before a recall loop, then use the returned canonical names::

        for f in validate_recall_fields('summary', 'created_at'):
            ...

    Every bad name is reported in one error rather than one per run, because
    the failure mode this guards against is a shotgun of guessed names.

    Args:
        fields: field names to check.
        allow_aliases: when True, a known alias resolves quietly instead of
            raising. Default False — an alias in source is a call site to fix,
            and this function exists to be stricter than attribute access.

    Returns:
        The canonical names, in the order given.

    Raises:
        RecallFieldError: if any name is unknown, or is an alias and
            ``allow_aliases`` is False.
    """
    if not fields:
        raise RecallFieldError("validate_recall_fields() needs at least one field name.")

    resolved, problems = [], []
    for field in fields:
        if not isinstance(field, str):
            problems.append(f"  {field!r} -> not a string")
            continue
        if field in VALID_FIELDS:
            resolved.append(field)
            continue
        hit = ALIASES.get(field)
        if hit and allow_aliases:
            resolved.append(hit)
            continue
        problems.append(_suggest(field))

    if problems:
        raise RecallFieldError(
            "Invalid recall() field name(s):\n"
            + "\n".join(problems)
            + "\n\nValid fields: "
            + ", ".join(sorted(VALID_FIELDS))
            + "\n\nNote: MemoryResult.to_dict() and .copy() return a PLAIN dict — "
            "a wrong field there returns the default silently instead of raising. "
            "Index the MemoryResult directly, or validate here first."
        )

    return tuple(resolved)
