"""
Tests for remembering.scripts.capabilities — trigger-first boot routing.

Pure filesystem tests: no Turso, no network. config_get is exercised via
patching; skill directories are built in tmp dirs. Safe to run anywhere,
same as the rest of remembering/tests/.
"""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import capabilities  # noqa: E402


def _make_skill(root: Path, name: str, description: str = None) -> None:
    d = root / name
    d.mkdir(parents=True)
    fm = f"---\nname: {name}\n"
    if description is not None:
        fm += f"description: {description}\n"
    fm += "---\n\n# body\n"
    (d / "SKILL.md").write_text(fm)


def _map(entries):
    return {"version": 1, "entries": entries}


class RenderMapPatch:
    """Context manager: patch the default map load to return `entries`."""

    def __init__(self, entries):
        self.patcher = patch.object(
            capabilities, "_load_capability_map", return_value=_map(entries)
        )

    def __enter__(self):
        return self.patcher.__enter__()

    def __exit__(self, *a):
        return self.patcher.__exit__(*a)


class TestSkillDescription(unittest.TestCase):
    def test_extracts_single_line_description(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_skill(root, "flowing", "DAG workflow runner. Use when 3+ steps.")
            self.assertEqual(
                capabilities._skill_description(root / "flowing"),
                "DAG workflow runner. Use when 3+ steps.",
            )

    def test_block_scalar_description_joins_continuation_lines(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / "blocky"
            d.mkdir()
            (d / "SKILL.md").write_text(
                "---\nname: blocky\ndescription: >-\n"
                "  First folded line\n  second folded line.\n"
                "metadata:\n  version: 1.0\n---\nbody\n"
            )
            self.assertEqual(
                capabilities._skill_description(d),
                "First folded line second folded line.",
            )

    def test_snippet_starts_at_use_when_clause(self):
        desc = "Fancy artifact blurb. Use when the task has shape X."
        self.assertEqual(
            capabilities._trigger_snippet(desc),
            "Use when the task has shape X.",
        )

    def test_missing_description_returns_none(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_skill(root, "bare")
            self.assertIsNone(capabilities._skill_description(root / "bare"))

    def test_missing_file_returns_none(self):
        self.assertIsNone(capabilities._skill_description(Path("/nonexistent/x")))


class TestTriggerSnippet(unittest.TestCase):
    def test_short_description_passes_through(self):
        self.assertEqual(capabilities._trigger_snippet("Use for X."), "Use for X.")

    def test_stops_at_sentence_boundary_under_cap(self):
        first = "Short first sentence."
        second = "S" * 200 + "."
        out = capabilities._trigger_snippet(f"{first} {second}")
        self.assertEqual(out, first)

    def test_single_overlong_sentence_hard_truncates_with_ellipsis(self):
        out = capabilities._trigger_snippet("x" * 400)
        self.assertLessEqual(len(out), capabilities._TRIGGER_MAX)
        self.assertTrue(out.endswith("…"))


class TestRenderTaskRouting(unittest.TestCase):
    def test_skill_entry_pulls_description_from_disk(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_skill(root, "flowing", "DAG workflow runner for 3+ step pipelines.")
            with RenderMapPatch([{"kind": "skill", "name": "flowing"}]):
                out = capabilities.render_task_routing(skills_dir=str(root))
        self.assertIn("DAG workflow runner for 3+ step pipelines.", out)
        self.assertIn("→ flowing skill", out)
        self.assertIn(f"{root}/flowing/SKILL.md", out)

    def test_skill_missing_from_disk_is_skipped(self):
        with TemporaryDirectory() as tmp:
            with RenderMapPatch([{"kind": "skill", "name": "ghost"}]):
                out = capabilities.render_task_routing(skills_dir=tmp)
        self.assertNotIn("ghost", out)

    def test_skill_when_override_beats_frontmatter(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_skill(root, "charting", "Frontmatter text.")
            entries = [{"kind": "skill", "name": "charting", "when": "Override trigger"}]
            with RenderMapPatch(entries):
                out = capabilities.render_task_routing(skills_dir=str(root))
        self.assertIn("Override trigger", out)
        self.assertNotIn("Frontmatter text.", out)

    def test_protocol_renders_verbatim_and_expands_skills_placeholder(self):
        with TemporaryDirectory() as tmp:
            entries = [{
                "kind": "protocol",
                "when": "Need a thing",
                "reach": "run {skills}/tool.py",
            }]
            with RenderMapPatch(entries):
                out = capabilities.render_task_routing(skills_dir=tmp)
        self.assertIn(f"Need a thing → run {tmp}/tool.py", out)

    def test_protocol_exists_probe_gates_row(self):
        with TemporaryDirectory() as tmp:
            present = {"kind": "protocol", "when": "A", "reach": "a",
                       "exists": tmp}
            absent = {"kind": "protocol", "when": "B", "reach": "b",
                      "exists": "/nonexistent/path"}
            with RenderMapPatch([present, absent]):
                out = capabilities.render_task_routing(skills_dir=tmp)
        self.assertIn("A → a", out)
        self.assertNotIn("B → b", out)

    def test_discovery_tail_counts_skills_and_points_at_finder(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_skill(root, "one", "d1")
            _make_skill(root, "two", "d2")
            finder = root / "finding-skills" / "scripts"
            finder.mkdir(parents=True)
            (finder / "skills.py").write_text("# finder")
            with RenderMapPatch([]):
                out = capabilities.render_task_routing(skills_dir=str(root))
        self.assertIn("2 skills on disk", out)
        self.assertIn("skills.py search <query>", out)

    def test_empty_environment_renders_empty(self):
        with TemporaryDirectory() as tmp:
            with RenderMapPatch([]):
                out = capabilities.render_task_routing(skills_dir=tmp)
        self.assertEqual(out, "")

    def test_bad_entry_does_not_sink_section(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_skill(root, "good", "Good trigger.")
            entries = [
                {"kind": "protocol"},          # missing when/reach
                {"kind": "skill"},             # missing name
                {"kind": "unknown"},           # unknown kind
                {"kind": "skill", "name": "good"},
            ]
            with RenderMapPatch(entries):
                out = capabilities.render_task_routing(skills_dir=str(root))
        self.assertIn("Good trigger.", out)


class TestLoadCapabilityMap(unittest.TestCase):
    def test_config_override_wins(self):
        override = json.dumps(_map([{"kind": "protocol", "when": "w", "reach": "r"}]))
        with patch("scripts.config.config_get", return_value=override):
            loaded = capabilities._load_capability_map()
        self.assertEqual(len(loaded["entries"]), 1)
        self.assertEqual(loaded["entries"][0]["when"], "w")

    def test_invalid_config_falls_back_to_repo_default(self):
        with patch("scripts.config.config_get", return_value="not json {"):
            loaded = capabilities._load_capability_map()
        # Repo default ships protocol + skill entries
        self.assertTrue(len(loaded["entries"]) > 0)
        kinds = {e.get("kind") for e in loaded["entries"]}
        self.assertIn("protocol", kinds)
        self.assertIn("skill", kinds)

    def test_config_error_falls_back_to_repo_default(self):
        with patch("scripts.config.config_get", side_effect=RuntimeError("no turso")):
            loaded = capabilities._load_capability_map()
        self.assertTrue(len(loaded["entries"]) > 0)

    def test_repo_default_is_valid_json_with_expected_shape(self):
        data = json.loads(capabilities._DEFAULT_MAP_PATH.read_text())
        self.assertIsInstance(data["entries"], list)
        for e in data["entries"]:
            self.assertIn(e["kind"], ("protocol", "skill"))
            if e["kind"] == "protocol":
                self.assertTrue(e["when"] and e["reach"])
            else:
                self.assertTrue(e["name"])


class TestRenderUtilities(unittest.TestCase):
    def test_trigger_first_lines(self):
        utils = {
            "bsky_card": {"use_when": "Posting a link to Bluesky with a card."},
            "remind": {"use_when": "Oskar says remind me."},
        }
        out = capabilities.render_utilities(utils)
        self.assertIn("Posting a link to Bluesky with a card. → bsky_card", out)
        self.assertIn("Oskar says remind me. → remind", out)
        self.assertIn("## Utilities (2", out)
        # Import path stated once in the heading, not per line
        self.assertIn("from muninn_utils import <name>", out)

    def test_unrouted_utils_collapse_to_roster_line(self):
        utils = {
            "routed": {"use_when": "When routed."},
            "bare_a": {"use_when": None},
            "bare_b": {},
        }
        out = capabilities.render_utilities(utils)
        self.assertIn("When routed. → routed", out)
        self.assertIn("(no use_when hint: bare_a, bare_b)", out)

    def test_empty_states_absence(self):
        out = capabilities.render_utilities({})
        self.assertIn("None installed", out)

    def test_long_use_when_is_snippeted(self):
        utils = {"x": {"use_when": "First sentence stays. " + "y" * 300 + "."}}
        out = capabilities.render_utilities(utils)
        self.assertIn("First sentence stays. → x", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
