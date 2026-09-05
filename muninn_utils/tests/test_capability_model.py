"""Tests for the capability model and the recovered mini-Muninn surface.

The load-bearing test is `test_read_only_expansion_refuses_a_writing_id`: it is the whole
reason this exists rather than a hand-curated module. Everything else guards the catalog
against drifting away from the code it names.
"""

from __future__ import annotations

import pathlib
import types

import pytest

from muninn_utils import capability_model as cm
from muninn_utils import mini_muninn

# -- the enforcement property ---------------------------------------------------


def test_read_only_expansion_refuses_a_writing_id():
    with pytest.raises(cm.WriteCapabilityRefused) as exc:
        cm.expand(["recall", "forget"], allow_writes=False)
    assert "forget" in str(exc.value)


def test_read_only_expansion_refuses_a_bundle_containing_a_writing_id():
    with pytest.raises(cm.WriteCapabilityRefused):
        cm.expand(["full"], allow_writes=False)


def test_mini_muninn_bundle_is_read_only():
    """The recovered surface, asserted rather than reviewed. If anyone adds a writing id to
    the bundle, mini_muninn.surface() raises at import-time and this fails."""
    caps = cm.resolve_ids(cm.BUNDLES["mini-muninn"])
    assert [c.id for c in caps if c.writes] == []


def test_mini_muninn_grants_exactly_the_recovered_surface():
    """Memory 81b2dc92: recall / batch / ops / ops-list / spokes, and deliberately no
    remember(), forget(), config_set(), or spokes mutation."""
    granted = set()
    for cap in cm.resolve_ids(cm.BUNDLES["mini-muninn"]):
        granted.update(cap.exports)
    for expected in ("recall", "recall_batch", "config_get", "config_list", "spokes_list"):
        assert expected in granted
    for forbidden in (
        "remember",
        "remember_batch",
        "forget",
        "supersede",
        "config_set",
        "set_rule",
        "spokes_add",
        "spokes_remove",
        "consolidate",
        "prune_by_age",
    ):
        assert forbidden not in granted, f"{forbidden} leaked into the read-only surface"


# -- requires -------------------------------------------------------------------


def test_unsatisfied_requirement_drops_the_capability_not_the_expansion(monkeypatch):
    """A subagent booted without a GitHub token should still get a working recall surface,
    with the spokes tools absent and explained — not a tool that 401s on first call."""
    monkeypatch.setitem(cm.REQUIREMENTS, "turso", lambda: True)
    monkeypatch.setitem(cm.REQUIREMENTS, "github", lambda: False)
    fake = types.SimpleNamespace(
        **{
            name: (lambda *a, **k: None)
            for cap in cm.CAPABILITIES.values()
            for name in cap.exports
        }
    )
    api = cm.expand(
        cm.BUNDLES["mini-muninn"], allow_writes=False, importer=lambda _m: fake
    )
    assert "recall" in api.functions
    assert "spokes_list" not in api.functions
    assert ("spokes-read", "github credentials absent") in api.dropped


def test_strict_requires_raises_instead_of_dropping(monkeypatch):
    monkeypatch.setitem(cm.REQUIREMENTS, "turso", lambda: False)
    with pytest.raises(RuntimeError, match="turso credentials absent"):
        cm.expand(["recall"], strict_requires=True, importer=lambda _m: object())


def test_unknown_id_raises_rather_than_shrinking_the_surface():
    """A typo must not silently hand out less than intended."""
    with pytest.raises(KeyError, match="reccall"):
        cm.resolve_ids(["reccall"])


# -- catalog/code agreement -----------------------------------------------------


def test_stale_catalog_entry_is_reported_not_swallowed(monkeypatch):
    monkeypatch.setitem(cm.REQUIREMENTS, "turso", lambda: True)
    empty = types.SimpleNamespace()
    api = cm.expand(["recall"], importer=lambda _m: empty)
    assert api.functions == {}
    assert api.dropped and "catalog is stale" in api.dropped[0][1]


def test_every_catalog_export_exists_upstream():
    """The catalog names real functions. This is the test that fails when someone renames a
    memory API and the subagent surface would otherwise quietly shrink."""
    import importlib

    stale = []
    for cap in cm.CAPABILITIES.values():
        try:
            module = importlib.import_module(cap.module)
        except ImportError as exc:  # pragma: no cover — environment-dependent
            pytest.skip(f"{cap.module} not importable here: {exc}")
        stale += [
            f"{cap.id}:{name}" for name in cap.exports if not hasattr(module, name)
        ]
    assert stale == []


def test_every_requirement_named_by_a_capability_is_defined():
    for cap in cm.CAPABILITIES.values():
        for need in cap.requires:
            assert need in cm.REQUIREMENTS, f"{cap.id} requires undefined {need!r}"


def test_describe_marks_write_capabilities():
    text = cm.describe(["recall", "forget"])
    assert "[read " in text and "[WRITE]" in text


# -- CLI ------------------------------------------------------------------------


def test_cli_capabilities_subcommand_runs_without_credentials(capsys):
    assert mini_muninn.main(["capabilities"]) == 0
    out = capsys.readouterr().out
    assert "recall" in out
    assert "spokes_add" not in out


def test_cli_never_names_a_write_function():
    """The read-only CLI should not reference a write API even in passing — if it does, the
    surface is being curated by hand again instead of generated."""
    source = pathlib.Path(mini_muninn.__file__).read_text(encoding="utf-8")
    for forbidden in ("remember(", "forget(", "config_set(", "spokes_add("):
        assert forbidden not in source, f"{forbidden} referenced in the read-only CLI"


def test_cli_dispatch_map_matches_the_granted_surface():
    """Every function the CLI dispatches to must be granted by the bundle."""
    granted = set()
    for cap in cm.resolve_ids(cm.BUNDLES["mini-muninn"]):
        granted.update(cap.exports)
    dispatched = {
        "recall",
        "recall_batch",
        "get",
        "get_chain",
        "config_get",
        "config_list",
        "spokes_list",
    }
    assert dispatched <= granted


# -- manifest audit reconciliation ----------------------------------------------


def test_declared_modules_covers_every_previously_unmanifested_module():
    """The nine the boot audit warned about, by name. A capability entry is the lighter
    declaration for a library-only module that has no use for an install-manifest."""
    previously_warned = {
        "bsky_moderation", "gh_proxy", "gh_status", "github_rw",
        "ruff_gate", "search_reindex", "skill_lint", "strava", "survey",
    }
    assert previously_warned <= cm.declared_modules()


def test_infrastructure_modules_are_declared_but_not_grantable():
    """They implement the capability layer; they are not capabilities."""
    grantable = {c.module.rsplit(".", 1)[-1] for c in cm.CAPABILITIES.values()}
    assert cm.INFRASTRUCTURE_MODULES.isdisjoint(grantable)
    assert cm.INFRASTRUCTURE_MODULES <= cm.declared_modules()
