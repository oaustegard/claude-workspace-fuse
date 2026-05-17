"""Tests for scripts/compose_layers.py — hub glue over container-layer skill.

Run from repo root:
    python3 -m unittest tests.test_compose_layers -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Import the module under test by path (not as a package — scripts/ isn't one).
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "compose_layers", REPO_ROOT / "scripts" / "compose_layers.py"
)
compose_layers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compose_layers)


class TestLayerPathAndName(unittest.TestCase):
    """Layer name <-> Containerfile path round-tripping."""

    def test_base_special_case(self):
        # 'base' maps to bare Containerfile (no suffix)
        p = compose_layers._layer_path("base")
        self.assertEqual(p.name, "Containerfile")

    def test_named_layers_use_suffix(self):
        for name in ("scientific", "torch-cpu", "mojo", "julia-sr"):
            p = compose_layers._layer_path(name)
            self.assertEqual(p.name, f"Containerfile.{name}")

    def test_name_from_path_reverse(self):
        self.assertEqual(
            compose_layers._layer_name(Path("/x/layers/Containerfile")), "base"
        )
        self.assertEqual(
            compose_layers._layer_name(Path("/x/layers/Containerfile.scientific")),
            "scientific",
        )
        self.assertEqual(
            compose_layers._layer_name(Path("/x/layers/Containerfile.torch-cpu")),
            "torch-cpu",
        )

    def test_name_from_path_fallback(self):
        # Non-Containerfile filename falls back to stem
        self.assertEqual(
            compose_layers._layer_name(Path("/x/weird-name.txt")), "weird-name"
        )


class TestReadManifest(unittest.TestCase):
    """Manifest reading: JSON parse, legacy fallback, missing-layer warning."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        (self.tmpdir / ".claude").mkdir()
        (self.tmpdir / "layers").mkdir()
        self._patches = [
            mock.patch.object(compose_layers, "PROJECT_DIR", self.tmpdir),
            mock.patch.object(
                compose_layers, "MANIFEST", self.tmpdir / ".claude" / "container-layers.json"
            ),
            mock.patch.object(compose_layers, "LAYERS_DIR", self.tmpdir / "layers"),
            mock.patch.object(
                compose_layers, "LEGACY_CONTAINERFILE", self.tmpdir / "Containerfile"
            ),
        ]
        for p in self._patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._patches])
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def _write_manifest(self, layers: list[str]):
        with open(self.tmpdir / ".claude" / "container-layers.json", "w") as f:
            json.dump({"layers": layers}, f)

    def _write_layer(self, name: str):
        target = (
            self.tmpdir / "layers" / "Containerfile"
            if name == "base"
            else self.tmpdir / "layers" / f"Containerfile.{name}"
        )
        target.write_text(f"RUN echo {name}\n")

    def test_manifest_returns_ordered_paths(self):
        self._write_manifest(["base", "scientific", "torch-cpu"])
        for n in ("base", "scientific", "torch-cpu"):
            self._write_layer(n)

        paths, legacy = compose_layers._read_manifest()
        self.assertFalse(legacy)
        self.assertEqual([p.name for p in paths], ["Containerfile", "Containerfile.scientific", "Containerfile.torch-cpu"])

    def test_missing_layer_is_skipped_with_warning(self):
        self._write_manifest(["base", "ghost", "scientific"])
        self._write_layer("base")
        self._write_layer("scientific")
        # NOTE: 'ghost' layer's Containerfile is intentionally absent

        with mock.patch("builtins.print") as mock_print:
            paths, legacy = compose_layers._read_manifest()

        names = [p.name for p in paths]
        self.assertEqual(names, ["Containerfile", "Containerfile.scientific"])
        # Verify the warning was printed
        warning_calls = [c for c in mock_print.call_args_list if "Skipping layers" in str(c)]
        self.assertEqual(len(warning_calls), 1)
        self.assertIn("ghost", str(warning_calls[0]))

    def test_legacy_fallback_when_no_manifest(self):
        # No manifest, but root Containerfile exists -> legacy mode
        (self.tmpdir / "Containerfile").write_text("RUN echo legacy\n")
        paths, legacy = compose_layers._read_manifest()
        self.assertTrue(legacy)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].name, "Containerfile")

    def test_no_manifest_no_legacy_returns_empty(self):
        paths, legacy = compose_layers._read_manifest()
        self.assertEqual(paths, [])
        self.assertFalse(legacy)

    def test_empty_layers_list_returns_empty(self):
        self._write_manifest([])
        paths, _ = compose_layers._read_manifest()
        self.assertEqual(paths, [])


class TestCompositeHash(unittest.TestCase):
    """Composite hash is deterministic and order-sensitive."""

    def test_same_inputs_same_hash(self):
        with mock.patch.object(compose_layers, "_cli") as mock_cli:
            mock_cli.side_effect = ["aaa", "bbb", "ccc"]
            h1 = compose_layers._composite_hash([Path("a"), Path("b"), Path("c")])
            mock_cli.side_effect = ["aaa", "bbb", "ccc"]
            h2 = compose_layers._composite_hash([Path("a"), Path("b"), Path("c")])
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 16)

    def test_order_matters(self):
        with mock.patch.object(compose_layers, "_cli") as mock_cli:
            mock_cli.side_effect = ["aaa", "bbb"]
            h_ab = compose_layers._composite_hash([Path("a"), Path("b")])
            mock_cli.side_effect = ["bbb", "aaa"]
            h_ba = compose_layers._composite_hash([Path("a"), Path("b")])
        self.assertNotEqual(
            h_ab, h_ba, "swapping layer order must produce a different composite hash"
        )

    def test_different_layer_hash_changes_composite(self):
        with mock.patch.object(compose_layers, "_cli") as mock_cli:
            mock_cli.side_effect = ["aaa", "bbb"]
            base = compose_layers._composite_hash([Path("a"), Path("b")])
            mock_cli.side_effect = ["aaa", "different"]
            changed = compose_layers._composite_hash([Path("a"), Path("b")])
        self.assertNotEqual(base, changed)


class TestCmdApply(unittest.TestCase):
    """cmd_apply dispatches to the right CLI invocation for each mode."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        (self.tmpdir / ".claude").mkdir()
        (self.tmpdir / "layers").mkdir()
        self._patches = [
            mock.patch.object(compose_layers, "PROJECT_DIR", self.tmpdir),
            mock.patch.object(
                compose_layers, "MANIFEST", self.tmpdir / ".claude" / "container-layers.json"
            ),
            mock.patch.object(compose_layers, "LAYERS_DIR", self.tmpdir / "layers"),
            mock.patch.object(
                compose_layers, "LEGACY_CONTAINERFILE", self.tmpdir / "Containerfile"
            ),
        ]
        for p in self._patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._patches])
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))
        # Redirect /tmp/.containerfile-hash to a temp file we own
        self.hash_file = self.tmpdir / "_hash"
        self._hash_patcher = mock.patch(
            "compose_layers.Path",
            side_effect=lambda x: self.hash_file if x == "/tmp/.containerfile-hash" else Path(x),
        )
        # Don't activate that patcher — too invasive. Just clean up after.
        self.addCleanup(
            lambda: Path("/tmp/.containerfile-hash").unlink(missing_ok=True)
            if Path("/tmp/.containerfile-hash").exists()
            else None
        )

    def _write_layer(self, name: str):
        target = (
            self.tmpdir / "layers" / "Containerfile"
            if name == "base"
            else self.tmpdir / "layers" / f"Containerfile.{name}"
        )
        target.write_text(f"RUN echo {name}\n")

    def test_legacy_mode_calls_restore(self):
        # No manifest, root Containerfile present
        (self.tmpdir / "Containerfile").write_text("RUN echo legacy\n")

        with mock.patch.object(compose_layers, "_cli") as mock_cli:
            mock_cli.return_value = "deadbeefcafebabe"
            compose_layers.cmd_apply()

        # First call is the restore; subsequent calls are hash queries
        restore_call = mock_cli.call_args_list[0]
        self.assertEqual(restore_call.args[0], "restore")
        # No --name flag in legacy mode
        self.assertNotIn("--name", restore_call.args)

    def test_single_named_layer_uses_restore_with_name(self):
        with open(self.tmpdir / ".claude" / "container-layers.json", "w") as f:
            json.dump({"layers": ["scientific"]}, f)
        self._write_layer("scientific")

        with mock.patch.object(compose_layers, "_cli") as mock_cli:
            mock_cli.return_value = "deadbeefcafebabe"
            compose_layers.cmd_apply()

        # First call should be `restore <path> --name scientific`
        first = mock_cli.call_args_list[0]
        self.assertEqual(first.args[0], "restore")
        self.assertIn("--name", first.args)
        self.assertIn("scientific", first.args)

    def test_multi_layer_uses_compose(self):
        with open(self.tmpdir / ".claude" / "container-layers.json", "w") as f:
            json.dump({"layers": ["base", "scientific", "torch-cpu"]}, f)
        for n in ("base", "scientific", "torch-cpu"):
            self._write_layer(n)

        with mock.patch.object(compose_layers, "_cli") as mock_cli:
            mock_cli.return_value = "deadbeefcafebabe"
            compose_layers.cmd_apply()

        first = mock_cli.call_args_list[0]
        self.assertEqual(first.args[0], "compose")
        # Three paths passed
        path_args = [a for a in first.args if a != "compose"]
        self.assertEqual(len(path_args), 3)

    def test_apply_with_no_layers_returns_silently(self):
        # No manifest, no legacy Containerfile
        with mock.patch.object(compose_layers, "_cli") as mock_cli:
            compose_layers.cmd_apply()
        mock_cli.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
