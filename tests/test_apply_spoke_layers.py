"""Tests for scripts/apply_spoke_layers.py — spoke-level layer overlay.

Run from repo root:
    python3 -m unittest tests.test_apply_spoke_layers -v
"""

import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Load both modules by path (scripts/ isn't a package).
_compose_spec = importlib.util.spec_from_file_location(
    "compose_layers", REPO_ROOT / "scripts" / "compose_layers.py"
)
compose_layers = importlib.util.module_from_spec(_compose_spec)
sys.modules["compose_layers"] = compose_layers  # so apply_spoke_layers's import resolves
_compose_spec.loader.exec_module(compose_layers)

_apply_spec = importlib.util.spec_from_file_location(
    "apply_spoke_layers", REPO_ROOT / "scripts" / "apply_spoke_layers.py"
)
apply_spoke_layers = importlib.util.module_from_spec(_apply_spec)
_apply_spec.loader.exec_module(apply_spoke_layers)
# Make sure the apply module shares our patched compose_layers
apply_spoke_layers.compose_layers = compose_layers


class _HubSpokeFixture(unittest.TestCase):
    """Shared scaffold: a temp hub dir with layers/ + .claude/ and a spoke under it."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.hub = self.tmpdir / "hub"
        self.hub.mkdir()
        (self.hub / ".claude").mkdir()
        (self.hub / "layers").mkdir()
        self.spokes = self.hub / ".spokes"
        self.spokes.mkdir()

        self._patches = [
            mock.patch.object(compose_layers, "PROJECT_DIR", self.hub),
            mock.patch.object(
                compose_layers, "MANIFEST", self.hub / ".claude" / "container-layers.json"
            ),
            mock.patch.object(compose_layers, "LAYERS_DIR", self.hub / "layers"),
            mock.patch.object(
                compose_layers, "LEGACY_CONTAINERFILE", self.hub / "Containerfile"
            ),
        ]
        for p in self._patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._patches])
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def _write_hub_manifest(self, layers: list):
        with open(self.hub / ".claude" / "container-layers.json", "w") as f:
            json.dump({"layers": layers}, f)

    def _write_hub_layer(self, name: str):
        target = (
            self.hub / "layers" / "Containerfile"
            if name == "base"
            else self.hub / "layers" / f"Containerfile.{name}"
        )
        target.write_text(f"RUN echo hub-{name}\n")

    def _make_spoke(self, name: str = "test-spoke") -> Path:
        spoke = self.spokes / name
        spoke.mkdir()
        (spoke / ".claude").mkdir()
        return spoke

    def _write_spoke_manifest(self, spoke: Path, extra: list):
        with open(spoke / ".claude" / "container-layers.json", "w") as f:
            json.dump({"extra": extra}, f)

    def _write_spoke_layer(self, spoke: Path, name: str):
        (spoke / "layers").mkdir(exist_ok=True)
        target = (
            spoke / "layers" / "Containerfile"
            if name == "base"
            else spoke / "layers" / f"Containerfile.{name}"
        )
        target.write_text(f"RUN echo spoke-{name}\n")


class TestReadSpokeManifest(_HubSpokeFixture):
    """Spoke manifest reading: absent, empty, present."""

    def test_no_manifest_returns_empty(self):
        spoke = self._make_spoke()
        self.assertEqual(apply_spoke_layers._read_spoke_manifest(spoke), [])

    def test_empty_extra_returns_empty(self):
        spoke = self._make_spoke()
        self._write_spoke_manifest(spoke, [])
        self.assertEqual(apply_spoke_layers._read_spoke_manifest(spoke), [])

    def test_missing_extra_key_returns_empty(self):
        spoke = self._make_spoke()
        with open(spoke / ".claude" / "container-layers.json", "w") as f:
            json.dump({"other": "thing"}, f)
        self.assertEqual(apply_spoke_layers._read_spoke_manifest(spoke), [])

    def test_ordered_extras_preserved(self):
        spoke = self._make_spoke()
        self._write_spoke_manifest(spoke, ["julia-sr", "mojo", "scientific"])
        self.assertEqual(
            apply_spoke_layers._read_spoke_manifest(spoke),
            ["julia-sr", "mojo", "scientific"],
        )


class TestReadHubActiveLayers(_HubSpokeFixture):
    """Hub manifest reading: absent, present, empty."""

    def test_no_hub_manifest_returns_empty(self):
        self.assertEqual(apply_spoke_layers._read_hub_active_layers(), [])

    def test_hub_manifest_returns_layers(self):
        self._write_hub_manifest(["base", "scientific", "torch-cpu"])
        self.assertEqual(
            apply_spoke_layers._read_hub_active_layers(),
            ["base", "scientific", "torch-cpu"],
        )

    def test_hub_manifest_empty_layers(self):
        self._write_hub_manifest([])
        self.assertEqual(apply_spoke_layers._read_hub_active_layers(), [])


class TestResolveLayerPath(_HubSpokeFixture):
    """Spoke-local Containerfile beats hub; hub fallback works; None when neither exists."""

    def test_resolves_from_hub_when_only_hub_has_it(self):
        self._write_hub_layer("julia-sr")
        spoke = self._make_spoke()
        path = apply_spoke_layers._resolve_layer_path("julia-sr", spoke)
        self.assertIsNotNone(path)
        self.assertEqual(path, self.hub / "layers" / "Containerfile.julia-sr")

    def test_resolves_from_spoke_when_only_spoke_has_it(self):
        spoke = self._make_spoke()
        self._write_spoke_layer(spoke, "custom")
        path = apply_spoke_layers._resolve_layer_path("custom", spoke)
        self.assertIsNotNone(path)
        self.assertEqual(path, spoke / "layers" / "Containerfile.custom")

    def test_spoke_overrides_hub_when_both_have_it(self):
        # Same-named layer in both — spoke wins (lets a spoke ship a fork)
        self._write_hub_layer("julia-sr")
        spoke = self._make_spoke()
        self._write_spoke_layer(spoke, "julia-sr")
        path = apply_spoke_layers._resolve_layer_path("julia-sr", spoke)
        self.assertEqual(path, spoke / "layers" / "Containerfile.julia-sr")

    def test_returns_none_when_neither_has_it(self):
        spoke = self._make_spoke()
        self.assertIsNone(apply_spoke_layers._resolve_layer_path("ghost", spoke))

    def test_base_special_case_no_suffix(self):
        # 'base' maps to bare Containerfile (no .base suffix) in either dir
        spoke = self._make_spoke()
        (spoke / "layers").mkdir()
        (spoke / "layers" / "Containerfile").write_text("RUN echo spoke-base\n")
        path = apply_spoke_layers._resolve_layer_path("base", spoke)
        self.assertEqual(path, spoke / "layers" / "Containerfile")


class TestComputeOverlay(_HubSpokeFixture):
    """Set-difference logic between spoke extras and active hub layers."""

    def test_no_spoke_manifest_yields_empty(self):
        spoke = self._make_spoke()
        to_apply, active, unresolved = apply_spoke_layers._compute_overlay(spoke)
        self.assertEqual(to_apply, [])
        self.assertEqual(active, [])
        self.assertEqual(unresolved, [])

    def test_empty_extra_yields_empty(self):
        spoke = self._make_spoke()
        self._write_spoke_manifest(spoke, [])
        to_apply, active, unresolved = apply_spoke_layers._compute_overlay(spoke)
        self.assertEqual(to_apply, [])

    def test_all_extras_already_in_hub(self):
        self._write_hub_manifest(["base", "scientific", "torch-cpu"])
        self._write_hub_layer("scientific")
        spoke = self._make_spoke()
        self._write_spoke_manifest(spoke, ["scientific", "torch-cpu"])
        to_apply, active, unresolved = apply_spoke_layers._compute_overlay(spoke)
        self.assertEqual(to_apply, [])
        self.assertEqual(active, ["scientific", "torch-cpu"])
        self.assertEqual(unresolved, [])

    def test_new_extras_collected_in_order(self):
        self._write_hub_manifest(["base"])
        self._write_hub_layer("julia-sr")
        self._write_hub_layer("mojo")
        spoke = self._make_spoke()
        self._write_spoke_manifest(spoke, ["mojo", "julia-sr"])
        to_apply, active, unresolved = apply_spoke_layers._compute_overlay(spoke)
        self.assertEqual(to_apply, ["mojo", "julia-sr"])
        self.assertEqual(active, [])

    def test_mixed_active_and_new(self):
        self._write_hub_manifest(["base", "scientific"])
        self._write_hub_layer("julia-sr")
        spoke = self._make_spoke()
        self._write_spoke_manifest(spoke, ["scientific", "julia-sr"])
        to_apply, active, unresolved = apply_spoke_layers._compute_overlay(spoke)
        self.assertEqual(to_apply, ["julia-sr"])
        self.assertEqual(active, ["scientific"])

    def test_unresolved_layer_reported_separately(self):
        self._write_hub_manifest(["base"])
        spoke = self._make_spoke()
        self._write_spoke_manifest(spoke, ["ghost", "missing"])
        to_apply, active, unresolved = apply_spoke_layers._compute_overlay(spoke)
        self.assertEqual(to_apply, [])
        self.assertEqual(unresolved, ["ghost", "missing"])

    def test_duplicates_in_extras_deduplicated(self):
        self._write_hub_manifest(["base"])
        self._write_hub_layer("julia-sr")
        spoke = self._make_spoke()
        self._write_spoke_manifest(spoke, ["julia-sr", "julia-sr"])
        to_apply, _, _ = apply_spoke_layers._compute_overlay(spoke)
        self.assertEqual(to_apply, ["julia-sr"])

    def test_spoke_defined_layer_resolves_from_spoke(self):
        # Layer not in hub at all — only the spoke ships its Containerfile
        self._write_hub_manifest(["base"])
        spoke = self._make_spoke()
        self._write_spoke_layer(spoke, "spoke-only")
        self._write_spoke_manifest(spoke, ["spoke-only"])
        to_apply, _, unresolved = apply_spoke_layers._compute_overlay(spoke)
        self.assertEqual(to_apply, ["spoke-only"])
        self.assertEqual(unresolved, [])

    def test_hub_defined_layer_not_in_hub_composition_still_applies(self):
        # Hub has Containerfile.julia-sr but doesn't include it in default
        # composition; spoke opts into it.
        self._write_hub_manifest(["base", "scientific"])
        self._write_hub_layer("julia-sr")  # Containerfile present, but not active
        spoke = self._make_spoke()
        self._write_spoke_manifest(spoke, ["julia-sr"])
        to_apply, active, unresolved = apply_spoke_layers._compute_overlay(spoke)
        self.assertEqual(to_apply, ["julia-sr"])
        self.assertEqual(active, [])
        self.assertEqual(unresolved, [])


class TestCmdApply(_HubSpokeFixture):
    """End-to-end cmd_apply: dispatches restore once per layer to apply, idempotent."""

    def test_no_manifest_is_noop(self):
        spoke = self._make_spoke()
        with mock.patch.object(compose_layers, "_cli") as mock_cli:
            with redirect_stdout(io.StringIO()):
                rc = apply_spoke_layers.cmd_apply(spoke)
        self.assertEqual(rc, 0)
        mock_cli.assert_not_called()

    def test_empty_extra_is_noop(self):
        spoke = self._make_spoke()
        self._write_spoke_manifest(spoke, [])
        with mock.patch.object(compose_layers, "_cli") as mock_cli:
            with redirect_stdout(io.StringIO()):
                rc = apply_spoke_layers.cmd_apply(spoke)
        self.assertEqual(rc, 0)
        mock_cli.assert_not_called()

    def test_all_extras_already_active_skips_all(self):
        self._write_hub_manifest(["base", "scientific", "torch-cpu"])
        spoke = self._make_spoke()
        self._write_spoke_manifest(spoke, ["scientific", "torch-cpu"])
        with mock.patch.object(compose_layers, "_cli") as mock_cli:
            with redirect_stdout(io.StringIO()):
                rc = apply_spoke_layers.cmd_apply(spoke)
        self.assertEqual(rc, 0)
        mock_cli.assert_not_called()

    def test_new_extras_invoke_restore_once_each(self):
        self._write_hub_manifest(["base", "scientific"])
        self._write_hub_layer("julia-sr")
        self._write_hub_layer("mojo")
        spoke = self._make_spoke()
        self._write_spoke_manifest(spoke, ["julia-sr", "mojo"])

        with mock.patch.object(compose_layers, "_cli") as mock_cli:
            with redirect_stdout(io.StringIO()):
                rc = apply_spoke_layers.cmd_apply(spoke)

        self.assertEqual(rc, 0)
        self.assertEqual(mock_cli.call_count, 2)
        first = mock_cli.call_args_list[0].args
        second = mock_cli.call_args_list[1].args
        self.assertEqual(first[0], "restore")
        self.assertIn("--name", first)
        self.assertIn("julia-sr", first)
        self.assertEqual(second[0], "restore")
        self.assertIn("--name", second)
        self.assertIn("mojo", second)

    def test_hub_layer_extra_resolves_to_hub_containerfile(self):
        # Hub has Containerfile.julia-sr but doesn't include it in active composition
        self._write_hub_manifest(["base", "scientific"])
        self._write_hub_layer("julia-sr")
        spoke = self._make_spoke()
        self._write_spoke_manifest(spoke, ["julia-sr"])

        with mock.patch.object(compose_layers, "_cli") as mock_cli:
            with redirect_stdout(io.StringIO()):
                rc = apply_spoke_layers.cmd_apply(spoke)

        self.assertEqual(rc, 0)
        self.assertEqual(mock_cli.call_count, 1)
        args = mock_cli.call_args_list[0].args
        # Path argument should be the hub's Containerfile.julia-sr
        path_arg = args[1]
        self.assertEqual(
            Path(path_arg), self.hub / "layers" / "Containerfile.julia-sr"
        )

    def test_spoke_layer_extra_resolves_to_spoke_containerfile(self):
        self._write_hub_manifest(["base"])
        spoke = self._make_spoke()
        self._write_spoke_manifest(spoke, ["spoke-only"])
        self._write_spoke_layer(spoke, "spoke-only")

        with mock.patch.object(compose_layers, "_cli") as mock_cli:
            with redirect_stdout(io.StringIO()):
                rc = apply_spoke_layers.cmd_apply(spoke)

        self.assertEqual(rc, 0)
        self.assertEqual(mock_cli.call_count, 1)
        args = mock_cli.call_args_list[0].args
        path_arg = args[1]
        self.assertEqual(
            Path(path_arg), spoke / "layers" / "Containerfile.spoke-only"
        )

    def test_unresolved_layer_is_skipped_with_warning(self):
        self._write_hub_manifest(["base"])
        spoke = self._make_spoke()
        self._write_spoke_manifest(spoke, ["ghost"])

        with mock.patch.object(compose_layers, "_cli") as mock_cli:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = apply_spoke_layers.cmd_apply(spoke)
        self.assertEqual(rc, 0)
        mock_cli.assert_not_called()
        self.assertIn("ghost", buf.getvalue())
        self.assertIn("no Containerfile", buf.getvalue())

    def test_missing_spoke_dir_returns_nonzero(self):
        with mock.patch.object(compose_layers, "_cli") as mock_cli:
            with redirect_stdout(io.StringIO()):
                rc = apply_spoke_layers.cmd_apply(self.tmpdir / "does-not-exist")
        self.assertEqual(rc, 2)
        mock_cli.assert_not_called()


class TestCmdInspect(_HubSpokeFixture):
    """Inspect mode must not invoke the skill CLI at all."""

    def test_inspect_does_not_call_cli(self):
        self._write_hub_manifest(["base"])
        self._write_hub_layer("julia-sr")
        spoke = self._make_spoke()
        self._write_spoke_manifest(spoke, ["julia-sr"])

        with mock.patch.object(compose_layers, "_cli") as mock_cli:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = apply_spoke_layers.cmd_inspect(spoke)

        self.assertEqual(rc, 0)
        mock_cli.assert_not_called()
        out = buf.getvalue()
        self.assertIn("julia-sr", out)
        self.assertIn("Would apply", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
