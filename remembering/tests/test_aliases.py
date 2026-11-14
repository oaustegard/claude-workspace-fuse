"""Tests for the holistic kwarg/return-shape fix (issue #15).

Three layers:

1. ``@accept_aliases`` decorator translates deprecated kwargs to canonical
   names and emits a ``DeprecationWarning``. Raises ``TypeError`` if both
   the wrong and right names are passed.
2. ``MemoryResult`` field aliases (``m.content`` → ``m.summary``) emit a
   ``DeprecationWarning`` instead of resolving silently.
3. ``MemoryWriteId`` — ``remember()`` / ``supersede()`` return a ``str``
   subclass exposing ``.id`` so the natural attribute-access pattern works
   on the write path without breaking ``str`` callers.

These tests are pure — they don't touch Turso. They exercise the
decorator and result-wrapper in isolation, plus a mocked ``remember()``
path to validate ``MemoryWriteId`` integration.
"""

import os
import sys
import warnings
from unittest.mock import patch

# Ensure the scripts package is importable when running this file directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Layer 1: accept_aliases decorator ──

def test_decorator_translates_kwarg_with_warning():
    """Calling recall(limit=5) translates to n=5 and emits DeprecationWarning."""
    from scripts.aliases import accept_aliases, ALIASES

    captured = {}

    # Define a dummy function with the same name `recall` so ALIASES['recall']
    # applies. Decorator looks up the table by func.__name__.
    @accept_aliases
    def recall(search=None, *, n=10, tags=None, type=None):
        captured["n"] = n
        captured["tags"] = tags
        captured["type"] = type
        return n

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = recall(limit=5)

    assert result == 5, "limit=5 should translate to n=5"
    assert captured["n"] == 5
    assert any(
        issubclass(w.category, DeprecationWarning) and "limit" in str(w.message)
        for w in caught
    ), "DeprecationWarning for 'limit' not emitted"
    print("PASS: decorator translates limit=5 -> n=5 with DeprecationWarning")


def test_decorator_translates_all_recall_aliases():
    """Each ALIASES['recall'] entry translates correctly."""
    from scripts.aliases import accept_aliases, ALIASES

    @accept_aliases
    def recall(search=None, *, n=10, tags=None, type=None):
        return {"n": n, "tags": tags, "type": type}

    cases = [
        ({"max_results": 7}, "n", 7),
        ({"count": 3}, "n", 3),
        ({"k": 4}, "n", 4),
        ({"keywords": ["a", "b"]}, "tags", ["a", "b"]),
        ({"types": "decision"}, "type", "decision"),
    ]
    for kwargs, expected_key, expected_val in cases:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = recall(**kwargs)
        assert result[expected_key] == expected_val, (
            f"recall({kwargs}) did not translate to {expected_key}={expected_val}"
        )
    print("PASS: decorator translates all recall aliases")


def test_decorator_raises_typeerror_on_both_names():
    """recall(limit=5, n=10) raises TypeError so callers don't get silent wins."""
    from scripts.aliases import accept_aliases

    @accept_aliases
    def recall(search=None, *, n=10):
        return n

    try:
        recall(limit=5, n=10)
    except TypeError as e:
        assert "limit" in str(e) and "n" in str(e), f"unexpected message: {e}"
        print("PASS: decorator raises TypeError when both names passed")
        return
    assert False, "Expected TypeError when both 'limit' and 'n' are passed"


def test_decorator_passes_through_canonical_kwargs():
    """No warning fires for canonical kwargs."""
    from scripts.aliases import accept_aliases

    @accept_aliases
    def remember(summary, type=None, *, tags=None):
        return (summary, type, tags)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = remember("hello", type="world", tags=["t"])

    assert result == ("hello", "world", ["t"])
    deprecation_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert not deprecation_warnings, (
        f"Did not expect deprecation warnings for canonical call, got: "
        f"{[str(w.message) for w in deprecation_warnings]}"
    )
    print("PASS: decorator passes through canonical kwargs cleanly")


def test_decorator_translates_remember_content_to_summary():
    """remember(content='x') translates to remember(summary='x') with warning."""
    from scripts.aliases import accept_aliases

    @accept_aliases
    def remember(summary, type=None, *, tags=None):
        return summary

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = remember(content="hello", type="world")

    assert result == "hello", "content=hello should translate to summary=hello"
    assert any(
        issubclass(w.category, DeprecationWarning) and "content" in str(w.message)
        for w in caught
    )
    print("PASS: remember(content=) -> remember(summary=) with warning")


def test_decorator_translates_remember_what_to_summary():
    """remember(what='x') translates to remember(summary='x') with warning (issue #17)."""
    from scripts.aliases import accept_aliases

    @accept_aliases
    def remember(summary, type=None, *, tags=None):
        return summary

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = remember(what="hello", type="world")

    assert result == "hello", "what=hello should translate to summary=hello"
    assert any(
        issubclass(w.category, DeprecationWarning) and "what" in str(w.message)
        for w in caught
    ), "DeprecationWarning for 'what' not emitted"
    print("PASS: remember(what=) -> remember(summary=) with warning (issue #17)")


def test_decorator_translates_supersede_content_to_summary():
    """supersede(id, content='x') translates content -> summary."""
    from scripts.aliases import accept_aliases

    @accept_aliases
    def supersede(original_id, summary, type, *, tags=None):
        return summary

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        # Pass summary as content kwarg; should land on summary positional param
        result = supersede("abc-123", content="new text", type="world")

    assert result == "new text"
    print("PASS: supersede(content=) -> supersede(summary=) translation works")


def test_decorator_no_aliases_returns_func_unchanged():
    """Functions without ALIASES entries are pass-through (no wrapper overhead)."""
    from scripts.aliases import accept_aliases

    @accept_aliases
    def nonexistent_function_no_aliases(x):
        return x

    # v5.12.0: the decorator now wraps every function (no fast-path) so it
    # can validate kwargs against the wrapped signature. Still pass-through
    # for valid calls, but the function object is wrapped.
    assert nonexistent_function_no_aliases(42) == 42
    print("PASS: no-aliases function is pass-through")


def test_decorator_unknown_kwarg_raises_informative_typeerror():
    """Unknown kwargs raise TypeError that includes the signature and aliases.

    v5.12.0: surfaces the wrapped function's real signature in the error
    message instead of leaving callers with Python's bare
    ``TypeError: got an unexpected keyword argument 'X'``.
    """
    from scripts.aliases import accept_aliases, ALIASES

    @accept_aliases
    def fake_supersede(original_id, summary, type, *, tags=None, conf=None, priority=None):
        return (original_id, summary, type, tags, conf, priority)

    # Make sure the alias table has a known entry for this function name so
    # the message includes the "Known aliases" hint. Use the real supersede
    # name so it picks up the production alias dict.
    fake_supersede.__name__ = "supersede"
    fake_supersede.__wrapped__.__name__ = "supersede"

    raised = None
    try:
        fake_supersede("id", "body", "decision", bogus_kwarg=1)
    except TypeError as e:
        raised = e

    assert raised is not None, "Unknown kwarg should raise TypeError"
    msg = str(raised)
    assert "bogus_kwarg" in msg, f"Error should name the offending kwarg; got: {msg}"
    assert "Signature:" in msg, f"Error should include the signature; got: {msg}"
    assert "priority" in msg, f"Signature should expose real kwargs; got: {msg}"
    print("PASS: unknown kwarg raises informative TypeError with signature")


def test_decorator_var_keyword_skips_validation():
    """Functions accepting **kwargs are exempt from the unknown-kwarg check."""
    from scripts.aliases import accept_aliases

    @accept_aliases
    def fn_with_kwargs(**kwargs):
        return kwargs

    # Should not raise even with a kwarg that's not in any alias table
    result = fn_with_kwargs(anything=1, whatever=2)
    assert result == {"anything": 1, "whatever": 2}
    print("PASS: **kwargs functions skip unknown-kwarg validation")


# ── Layer 2: MemoryResult field aliases warn ──

def test_memory_result_attr_alias_warns():
    """m.content emits DeprecationWarning, resolves to m.summary."""
    from scripts.result import MemoryResult

    m = MemoryResult({"id": "abc", "summary": "hello", "type": "world"})

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        value = m.content

    assert value == "hello", f"m.content should resolve to m.summary, got {value!r}"
    assert any(
        issubclass(w.category, DeprecationWarning) and "content" in str(w.message)
        for w in caught
    ), "m.content should emit DeprecationWarning"
    print("PASS: MemoryResult.content emits DeprecationWarning and resolves to summary")


def test_memory_result_item_alias_warns():
    """m['content'] emits DeprecationWarning, resolves to m['summary']."""
    from scripts.result import MemoryResult

    m = MemoryResult({"id": "abc", "summary": "hello", "type": "world"})

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        value = m["content"]

    assert value == "hello"
    assert any(
        issubclass(w.category, DeprecationWarning) and "content" in str(w.message)
        for w in caught
    )
    print("PASS: m['content'] emits DeprecationWarning")


def test_memory_result_get_alias_warns():
    """m.get('content') emits DeprecationWarning, resolves to m.get('summary')."""
    from scripts.result import MemoryResult

    m = MemoryResult({"id": "abc", "summary": "hello", "type": "world"})

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        value = m.get("content")

    assert value == "hello"
    assert any(
        issubclass(w.category, DeprecationWarning) and "content" in str(w.message)
        for w in caught
    )
    print("PASS: m.get('content') emits DeprecationWarning")


def test_memory_result_canonical_field_no_warn():
    """m.summary (canonical name) does not emit DeprecationWarning."""
    from scripts.result import MemoryResult

    m = MemoryResult({"id": "abc", "summary": "hello", "type": "world"})

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _ = m.summary
        _ = m["id"]
        _ = m.get("type")

    deps = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert not deps, f"Canonical fields should not warn, got: {[str(w.message) for w in deps]}"
    print("PASS: canonical MemoryResult fields don't warn")


# ── Layer 3: MemoryWriteId behaves as str with .id ──

def test_memory_write_id_is_str_subclass():
    """MemoryWriteId is a str — equality, hashing, json work as expected."""
    from scripts.aliases import MemoryWriteId
    import json

    m = MemoryWriteId("550e8400-e29b-41d4-a716-446655440000")

    assert isinstance(m, str)
    assert m == "550e8400-e29b-41d4-a716-446655440000"
    assert hash(m) == hash("550e8400-e29b-41d4-a716-446655440000")
    assert json.dumps(m) == '"550e8400-e29b-41d4-a716-446655440000"'
    assert len(m) == 36
    print("PASS: MemoryWriteId is a true str subclass")


def test_memory_write_id_exposes_dot_id():
    """m.id returns the string itself — fixes the `m.id` access pattern."""
    from scripts.aliases import MemoryWriteId

    raw = "550e8400-e29b-41d4-a716-446655440000"
    m = MemoryWriteId(raw)

    assert m.id == raw
    assert m.id is not None
    print("PASS: MemoryWriteId.id returns the underlying string")


def test_memory_write_id_repr():
    """repr is distinguishable from bare str."""
    from scripts.aliases import MemoryWriteId

    m = MemoryWriteId("abc")
    assert "MemoryWriteId" in repr(m)
    print("PASS: MemoryWriteId.__repr__ surfaces the wrapper")


def test_remember_returns_memory_write_id():
    """remember() integration: returns MemoryWriteId, .id accessible."""
    from scripts.aliases import MemoryWriteId

    # Patch the inner _write_memory to avoid Turso. We exercise the public
    # remember() path end-to-end so the return-shape change is verified
    # at the actual API boundary, not just on the helper.
    with patch("scripts.memory._write_memory"), \
         patch("scripts.memory.config_get", return_value=None), \
         patch("scripts.memory.config_set"):
        from scripts.memory import remember

        result = remember("test memory", "world", tags=["t"])

    assert isinstance(result, MemoryWriteId), (
        f"remember() should return MemoryWriteId, got {type(result).__name__}"
    )
    assert isinstance(result, str), "MemoryWriteId must remain a str"
    assert result.id == str(result)
    # The id is a UUID, so it's 36 chars with 4 hyphens
    assert len(result) == 36
    print("PASS: remember() returns MemoryWriteId with .id accessible")


def test_remember_back_compat_as_string():
    """remember()'s return still works in str contexts (back-compat)."""
    with patch("scripts.memory._write_memory"), \
         patch("scripts.memory.config_get", return_value=None), \
         patch("scripts.memory.config_set"):
        from scripts.memory import remember

        mem_id = remember("test", "world")

    # Equality with bare string
    assert mem_id == str(mem_id)
    # Concatenation
    assert ("prefix:" + mem_id).startswith("prefix:")
    # Use in f-string
    assert f"id={mem_id}".startswith("id=")
    print("PASS: remember() return value works as a plain string")


def test_remember_content_alias_works():
    """remember(content='x') translates to summary='x' through the decorator."""
    with patch("scripts.memory._write_memory") as mock_write, \
         patch("scripts.memory.config_get", return_value=None), \
         patch("scripts.memory.config_set"):
        from scripts.memory import remember

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            mem_id = remember(content="hello", type="world")

    # Verify _write_memory was called with summary='hello' at position 1
    args, _ = mock_write.call_args
    # _write_memory(mem_id, summary, type, now, conf, tags, refs, priority, valid_from, session_id)
    assert args[1] == "hello", f"summary should be 'hello', got {args[1]!r}"
    assert args[2] == "world", f"type should be 'world', got {args[2]!r}"
    print("PASS: remember(content='hello') translates to summary='hello' through decorator")


def test_remember_what_alias_works():
    """remember(what='x') translates to summary='x' through the decorator (issue #17)."""
    with patch("scripts.memory._write_memory") as mock_write, \
         patch("scripts.memory.config_get", return_value=None), \
         patch("scripts.memory.config_set"):
        from scripts.memory import remember

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            mem_id = remember(what="hello", type="world")

    args, _ = mock_write.call_args
    assert args[1] == "hello", f"summary should be 'hello', got {args[1]!r}"
    assert any(
        issubclass(w.category, DeprecationWarning) and "what" in str(w.message)
        for w in caught
    ), "remember(what=) should warn"
    print("PASS: remember(what='hello') translates to summary='hello' with warning (issue #17)")


def test_remember_summary_canonical_no_warn():
    """remember(summary='x', ...) — canonical kwarg, no DeprecationWarning (issue #17)."""
    with patch("scripts.memory._write_memory") as mock_write, \
         patch("scripts.memory.config_get", return_value=None), \
         patch("scripts.memory.config_set"):
        from scripts.memory import remember

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            mem_id = remember(summary="hello", type="world")

    args, _ = mock_write.call_args
    assert args[1] == "hello", f"summary should be 'hello', got {args[1]!r}"
    deps = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert not deps, (
        f"remember(summary=...) is canonical and must not warn, got: "
        f"{[str(w.message) for w in deps]}"
    )
    print("PASS: remember(summary='hello') is canonical and emits no warning (issue #17)")


def test_remember_batch_what_alias_warns():
    """remember_batch items with 'what' key translate to 'summary' with warning (issue #17)."""
    with patch("scripts.memory._exec_batch") as mock_batch, \
         patch("scripts.memory.config_get", return_value=None), \
         patch("scripts.memory.config_set"), \
         patch("scripts.memory.get_session_id", return_value="test-session"):
        from scripts.memory import remember_batch

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ids = remember_batch([
                {"what": "via deprecated alias", "type": "world"},
                {"summary": "via canonical key", "type": "world"},
            ])

    # Both items wrote
    assert mock_batch.called
    statements = mock_batch.call_args[0][0]
    assert len(statements) == 2, f"expected 2 INSERTs, got {len(statements)}"
    # SQL params order: [mem_id, type, now, summary, conf, ...]
    summaries = [stmt[1][3] for stmt in statements]
    assert "via deprecated alias" in summaries
    assert "via canonical key" in summaries

    # The 'what' alias should warn; the canonical key should not.
    what_warnings = [
        w for w in caught
        if issubclass(w.category, DeprecationWarning) and "what" in str(w.message)
    ]
    assert what_warnings, "remember_batch with item 'what' key should DeprecationWarn"
    print("PASS: remember_batch({'what': ...}) translates to summary with warning (issue #17)")


def test_recall_limit_alias_warns_then_translates():
    """Calling recall(limit=5) hits the decorator; warns; translates to n=5."""
    # Patch the Turso layer so recall() doesn't hit the network.
    with patch("scripts.memory._fts5_search", return_value=[]) as mock_fts5, \
         patch("scripts.memory._retry_with_backoff", side_effect=lambda fn, **kw: fn()):
        from scripts.memory import recall

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            recall("test query", limit=5)

    assert any(
        issubclass(w.category, DeprecationWarning) and "limit" in str(w.message)
        for w in caught
    ), "recall(limit=) should warn"
    # _fts5_search should have been called with n=5
    _, kwargs = mock_fts5.call_args
    assert kwargs.get("n") == 5, f"recall(limit=5) did not propagate as n=5: {kwargs}"
    print("PASS: recall(limit=5) warns and translates to n=5")


# ── Smoke: ALIASES table sanity ──

def test_aliases_table_no_self_referential_entries():
    """No wrong→right entry maps a name to itself (would loop)."""
    from scripts.aliases import ALIASES

    for fname, mapping in ALIASES.items():
        for wrong, right in mapping.items():
            assert wrong != right, (
                f"ALIASES[{fname!r}][{wrong!r}] maps to itself"
            )
    print("PASS: ALIASES table has no self-referential entries")


def test_aliases_table_covers_issue_15_examples():
    """ALIASES covers the specific examples called out in issue #15."""
    from scripts.aliases import ALIASES

    # Issue #15 examples for recall
    for wrong in ("max_results", "count", "k", "limit", "keywords", "types"):
        assert wrong in ALIASES["recall"], (
            f"ALIASES['recall'] missing {wrong!r} (issue #15)"
        )

    # Issue #15 examples for remember; issue #17 added `what` as a deprecated alias
    for wrong in ("content", "body", "text", "keywords", "what"):
        assert wrong in ALIASES["remember"], (
            f"ALIASES['remember'] missing {wrong!r}"
        )

    # Issue #15 examples for supersede
    for wrong in ("content", "body"):
        assert wrong in ALIASES["supersede"], (
            f"ALIASES['supersede'] missing {wrong!r} (issue #15)"
        )

    # Canonical targets. Issue #17: remember canonical reverted to `summary`
    # so the whole write+read surface uses one name.
    assert ALIASES["recall"]["max_results"] == "n"
    assert ALIASES["recall"]["keywords"] == "tags"
    assert ALIASES["recall"]["types"] == "type"
    assert ALIASES["remember"]["content"] == "summary"
    assert ALIASES["remember"]["what"] == "summary"
    assert ALIASES["supersede"]["content"] == "summary"

    print("PASS: ALIASES covers all examples called out in issues #15 and #17")


# ── Export surface ──

def test_public_exports():
    """scripts.__init__ exports MemoryWriteId, ALIASES, accept_aliases."""
    import scripts

    assert "MemoryWriteId" in scripts.__all__
    assert "ALIASES" in scripts.__all__
    assert "accept_aliases" in scripts.__all__

    from scripts import MemoryWriteId, ALIASES, accept_aliases  # noqa: F401
    print("PASS: aliases module exports surface correctly")


if __name__ == "__main__":
    tests = [
        # Layer 1: decorator
        test_decorator_translates_kwarg_with_warning,
        test_decorator_translates_all_recall_aliases,
        test_decorator_raises_typeerror_on_both_names,
        test_decorator_passes_through_canonical_kwargs,
        test_decorator_translates_remember_content_to_summary,
        test_decorator_translates_remember_what_to_summary,
        test_decorator_translates_supersede_content_to_summary,
        test_decorator_no_aliases_returns_func_unchanged,
        test_decorator_unknown_kwarg_raises_informative_typeerror,
        test_decorator_var_keyword_skips_validation,
        # Layer 2: field aliases
        test_memory_result_attr_alias_warns,
        test_memory_result_item_alias_warns,
        test_memory_result_get_alias_warns,
        test_memory_result_canonical_field_no_warn,
        # Layer 3: MemoryWriteId
        test_memory_write_id_is_str_subclass,
        test_memory_write_id_exposes_dot_id,
        test_memory_write_id_repr,
        test_remember_returns_memory_write_id,
        test_remember_back_compat_as_string,
        test_remember_content_alias_works,
        test_remember_what_alias_works,
        test_remember_summary_canonical_no_warn,
        test_remember_batch_what_alias_warns,
        test_recall_limit_alias_warns_then_translates,
        # Sanity
        test_aliases_table_no_self_referential_entries,
        test_aliases_table_covers_issue_15_examples,
        test_public_exports,
    ]
    failed = []
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            failed.append(t.__name__)
            import traceback
            traceback.print_exc()
    print()
    print(f"Ran {len(tests)} tests, {len(failed)} failed")
    if failed:
        sys.exit(1)
