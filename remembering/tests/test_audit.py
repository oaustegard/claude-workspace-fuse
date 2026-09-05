"""
Tests for remembering.scripts.audit — boot-time manifest audit.

Per oaustegard/muninn-utilities#6, the audit checks four things at boot:
1. Manifest exists and parses (warn-quiet on bad JSON / missing file).
2. Declared `env[].required: true` vars resolve to non-empty values.
3. Declared `scopes[]` plus declared `env[]` cover what the utility source
   actually references — flag drift in either direction.
4. manifests/ directory and muninn_utils/*.py module list match in count.

The audit must NEVER raise. Default policy is warn-quiet: emit a one-line
summary to the boot output plus structured warnings to stderr.
"""

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr

# Make remembering.scripts importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import audit


# ── helpers ─────────────────────────────────────────────────────────

VALID_MANIFEST = {
    "manifest_version": "0.3",
    "tool": {
        "id": "muninn-test",
        "version": "0.1.0",
        "name": "Test Tool",
        "summary": "A minimal valid manifest for tests.",
        "homepage": "https://example.com/",
    },
    "runtime": {
        "kind": "python-module",
        "install": {
            "method": "git",
            "url": "https://github.com/example/repo",
            "ref": "deadbeef",
        },
        "entrypoint": {"command": ["python", "-m", "fake"]},
    },
    "env": [
        {"name": "TEST_TOKEN", "prompt": "tok", "secret": True, "required": True},
        {"name": "TEST_OPTIONAL", "prompt": "opt", "secret": False, "required": False},
    ],
    "scopes": [
        {
            "resource": "compute.local",
            "actions": ["read"],
            "rationale": "test",
        }
    ],
    "actions": [
        {
            "name": "noop",
            "summary": "do nothing",
            "invocation": {"kind": "stdin-json"},
            "side_effects": "none",
        }
    ],
    "smoke": {
        "kind": "shell",
        "command": ["true"],
        "success": {"exit_code": 0},
    },
    "kill_switch": {"kind": "manual", "instructions_url": "https://example.com/REVOKE"},
}


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def _write_manifest(path, manifest):
    _write(path, json.dumps(manifest, indent=2))


# ── 1. load_manifest ────────────────────────────────────────────────

def test_load_manifest_valid_returns_dict():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "m.json")
        _write_manifest(path, VALID_MANIFEST)
        result = audit.load_manifest(path)
        assert isinstance(result, dict)
        assert result["manifest_version"] == "0.3"
        assert result["tool"]["id"] == "muninn-test"


def test_load_manifest_invalid_json_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "broken.json")
        _write(path, "{not valid json")
        result = audit.load_manifest(path)
        assert result is None, "broken JSON should return None, not raise"


def test_load_manifest_missing_file_returns_none():
    result = audit.load_manifest("/tmp/this-path-does-not-exist-12345.json")
    assert result is None, "missing file should return None, not raise"


# ── 2. check_env_loadable ───────────────────────────────────────────

def test_check_env_loadable_all_required_set():
    env = {"TEST_TOKEN": "abc", "TEST_OPTIONAL": "x"}
    missing = audit.check_env_loadable(VALID_MANIFEST, env)
    assert missing == [], f"expected [], got {missing}"


def test_check_env_loadable_required_missing():
    env = {"TEST_OPTIONAL": "x"}  # TEST_TOKEN absent
    missing = audit.check_env_loadable(VALID_MANIFEST, env)
    assert "TEST_TOKEN" in missing
    assert "TEST_OPTIONAL" not in missing


def test_check_env_loadable_required_empty_string_counts_as_missing():
    """A required env var set to empty string is effectively unset."""
    env = {"TEST_TOKEN": "", "TEST_OPTIONAL": ""}
    missing = audit.check_env_loadable(VALID_MANIFEST, env)
    assert "TEST_TOKEN" in missing
    assert "TEST_OPTIONAL" not in missing  # optional, blank is fine


def test_check_env_loadable_optional_unset_does_not_warn():
    env = {"TEST_TOKEN": "abc"}
    missing = audit.check_env_loadable(VALID_MANIFEST, env)
    assert missing == []


def test_check_env_loadable_handles_manifest_without_env():
    manifest = dict(VALID_MANIFEST)
    manifest.pop("env", None)
    missing = audit.check_env_loadable(manifest, {})
    assert missing == []


# ── 3. detect_scope_drift ───────────────────────────────────────────

def test_scope_drift_clean_when_source_uses_only_declared_env():
    source = """
import os
def f():
    return os.environ.get("TEST_TOKEN")
"""
    drift = audit.detect_scope_drift(source, VALID_MANIFEST)
    assert drift["used_not_declared"] == []


def test_scope_drift_flags_env_used_but_not_declared():
    """Source pulls GH_TOKEN that the manifest never lists."""
    source = """
import os
token = os.environ.get("GH_TOKEN")
secret = os.environ["UNDECLARED_SECRET"]
"""
    drift = audit.detect_scope_drift(source, VALID_MANIFEST)
    assert "GH_TOKEN" in drift["used_not_declared"]
    assert "UNDECLARED_SECRET" in drift["used_not_declared"]


def test_scope_drift_flags_env_declared_but_not_used():
    source = "x = 1\n"  # references nothing
    drift = audit.detect_scope_drift(source, VALID_MANIFEST)
    assert "TEST_TOKEN" in drift["declared_not_used"]


def test_scope_drift_recognizes_os_getenv_form():
    source = "import os\nx = os.getenv('TEST_TOKEN')\n"
    drift = audit.detect_scope_drift(source, VALID_MANIFEST)
    # TEST_TOKEN is matched by os.getenv form, so it's not in declared_not_used.
    assert "TEST_TOKEN" not in drift["declared_not_used"]
    assert drift["used_not_declared"] == []


def test_scope_drift_ignores_local_variable_named_like_env_var():
    """Heuristic should only catch os.environ / os.getenv access patterns."""
    source = """
def f():
    GH_TOKEN = "literal"  # not an env read
    return GH_TOKEN
"""
    drift = audit.detect_scope_drift(source, VALID_MANIFEST)
    assert "GH_TOKEN" not in drift["used_not_declared"]


def test_scope_drift_indirect_entry_skips_declared_not_used():
    """Manifest entries with `indirect: true` are required-but-transitively-accessed.

    The static regex can't see them (e.g. read by a downstream library, or by
    dynamic key like `os.environ[var_name_arg]`). They should not trigger
    declared-not-used drift even when absent from the source.
    """
    manifest = {
        "manifest_version": "0.3",
        "env": [
            {"name": "TURSO_TOKEN", "required": True, "indirect": True},
            {"name": "TURSO_URL", "required": True, "indirect": True},
            {"name": "GH_TOKEN", "required": True},
        ],
    }
    source = "import os\ntoken = os.environ.get('GH_TOKEN')\n"
    drift = audit.detect_scope_drift(source, manifest)
    assert drift["declared_not_used"] == []  # TURSO_* suppressed by indirect
    assert drift["used_not_declared"] == []  # GH_TOKEN is declared


def test_scope_drift_indirect_entry_does_not_suppress_used_not_declared():
    """Indirect only opts out of declared-not-used; used-not-declared still fires."""
    manifest = {
        "manifest_version": "0.3",
        "env": [
            {"name": "TURSO_TOKEN", "required": True, "indirect": True},
        ],
    }
    source = "import os\ntoken = os.environ.get('UNDECLARED_VAR')\n"
    drift = audit.detect_scope_drift(source, manifest)
    assert "UNDECLARED_VAR" in drift["used_not_declared"]


def test_scope_drift_indirect_false_or_missing_does_not_suppress():
    """`indirect: false` or absent field → entry participates in drift normally."""
    manifest = {
        "manifest_version": "0.3",
        "env": [
            {"name": "ZAP_TOKEN", "required": True, "indirect": False},
            {"name": "QUUX_URL", "required": True},  # no indirect field
        ],
    }
    source = "import os\n"  # nothing read
    drift = audit.detect_scope_drift(source, manifest)
    assert sorted(drift["declared_not_used"]) == ["QUUX_URL", "ZAP_TOKEN"]


# ── 4. index_diff ───────────────────────────────────────────────────

def test_index_diff_clean_when_modules_match_manifests():
    with tempfile.TemporaryDirectory() as tmp:
        manifests = os.path.join(tmp, "manifests")
        modules = os.path.join(tmp, "muninn_utils")
        os.makedirs(os.path.join(manifests, "foo"))
        os.makedirs(modules)
        _write_manifest(os.path.join(manifests, "foo", "muninn-foo.v0.3.json"), VALID_MANIFEST)
        _write(os.path.join(modules, "foo.py"), "# stub")

        diff = audit.index_diff(manifests, modules)
        assert diff["manifests_only"] == []
        assert diff["modules_only"] == []


def test_index_diff_reports_module_without_manifest():
    with tempfile.TemporaryDirectory() as tmp:
        manifests = os.path.join(tmp, "manifests")
        modules = os.path.join(tmp, "muninn_utils")
        os.makedirs(manifests)
        os.makedirs(modules)
        _write(os.path.join(modules, "lonely.py"), "# stub")

        diff = audit.index_diff(manifests, modules)
        assert "lonely" in diff["modules_only"]


def test_index_diff_reports_manifest_without_module():
    with tempfile.TemporaryDirectory() as tmp:
        manifests = os.path.join(tmp, "manifests")
        modules = os.path.join(tmp, "muninn_utils")
        os.makedirs(os.path.join(manifests, "ghost"))
        os.makedirs(modules)
        _write_manifest(os.path.join(manifests, "ghost", "muninn-ghost.v0.3.json"), VALID_MANIFEST)

        diff = audit.index_diff(manifests, modules)
        assert "ghost" in diff["manifests_only"]


def test_index_diff_ignores_dunder_and_tests_dir():
    with tempfile.TemporaryDirectory() as tmp:
        manifests = os.path.join(tmp, "manifests")
        modules = os.path.join(tmp, "muninn_utils")
        os.makedirs(manifests)
        os.makedirs(os.path.join(modules, "tests"))
        _write(os.path.join(modules, "__init__.py"), "")
        _write(os.path.join(modules, "tests", "test_foo.py"), "")

        diff = audit.index_diff(manifests, modules)
        assert "__init__" not in diff["modules_only"]
        # tests/ is a directory, not a .py at the top level — should be ignored anyway.


def test_index_diff_ignores_flowing_reexport_shim():
    """`flowing` re-exports the canonical /mnt/skills/user/flowing/ skill,
    so it has no install surface of its own and should be skipped."""
    with tempfile.TemporaryDirectory() as tmp:
        manifests = os.path.join(tmp, "manifests")
        modules = os.path.join(tmp, "muninn_utils")
        os.makedirs(manifests)
        os.makedirs(modules)
        _write(os.path.join(modules, "flowing.py"), "# re-export shim")

        diff = audit.index_diff(manifests, modules)
        assert "flowing" not in diff["modules_only"]


# ── 5. full audit() ─────────────────────────────────────────────────

def _make_repo(tmp, mods_with_manifests, env_drift_mod=None):
    """Build a fake repo with `manifests/` and `muninn_utils/` subdirs.

    mods_with_manifests: list of (mod_name, source_text, env_keys) tuples.
    env_drift_mod: if set, that module's source also reads GH_TOKEN
                   without the manifest declaring it.
    """
    manifests = os.path.join(tmp, "manifests")
    modules = os.path.join(tmp, "muninn_utils")
    os.makedirs(manifests)
    os.makedirs(modules)
    for name, src, env_keys in mods_with_manifests:
        manifest = json.loads(json.dumps(VALID_MANIFEST))  # deep copy
        manifest["tool"]["id"] = f"muninn-{name}"
        manifest["env"] = [
            {"name": k, "prompt": "p", "secret": False, "required": True}
            for k in env_keys
        ]
        _write_manifest(
            os.path.join(manifests, name, f"muninn-{name}.v0.3.json"),
            manifest,
        )
        full_src = src
        if env_drift_mod == name:
            full_src = "import os\ntok = os.environ['GH_TOKEN']\n" + src
        _write(os.path.join(modules, f"{name}.py"), full_src)
    return manifests, modules


def test_audit_returns_dict_with_summary_and_warnings_keys():
    with tempfile.TemporaryDirectory() as tmp:
        manifests, modules = _make_repo(tmp, [("foo", "# stub", [])])
        result = audit.audit(manifests, modules, env={})
        assert "summary" in result
        assert "warnings" in result
        assert isinstance(result["summary"], str)
        assert isinstance(result["warnings"], list)


def test_audit_summary_reports_audited_count():
    with tempfile.TemporaryDirectory() as tmp:
        manifests, modules = _make_repo(
            tmp,
            [("foo", "# stub", []), ("bar", "# stub", [])],
        )
        result = audit.audit(manifests, modules, env={})
        # The summary should be a single line mentioning audited counts.
        assert "\n" not in result["summary"], "summary must be one line"
        assert "2" in result["summary"]


def test_audit_flags_unconfigured_required_env():
    with tempfile.TemporaryDirectory() as tmp:
        manifests, modules = _make_repo(
            tmp, [("foo", "# stub", ["NEEDED_TOKEN"])]
        )
        result = audit.audit(manifests, modules, env={})
        joined = " ".join(result["warnings"])
        assert "NEEDED_TOKEN" in joined
        assert "foo" in joined


def test_audit_flags_scope_drift():
    with tempfile.TemporaryDirectory() as tmp:
        manifests, modules = _make_repo(
            tmp,
            [("foo", "# stub", [])],
            env_drift_mod="foo",
        )
        result = audit.audit(manifests, modules, env={"GH_TOKEN": "x"})
        joined = " ".join(result["warnings"])
        assert "GH_TOKEN" in joined


def test_audit_flags_index_drift():
    """A module without a manifest is reported."""
    with tempfile.TemporaryDirectory() as tmp:
        manifests, modules = _make_repo(tmp, [])
        _write(os.path.join(modules, "orphan.py"), "# no manifest")
        result = audit.audit(manifests, modules, env={})
        joined = " ".join(result["warnings"])
        assert "orphan" in joined


def test_audit_does_not_raise_on_empty_manifest_dir():
    """Stub-form audit: zero manifests — should still return without raising."""
    with tempfile.TemporaryDirectory() as tmp:
        manifests = os.path.join(tmp, "manifests")
        modules = os.path.join(tmp, "muninn_utils")
        os.makedirs(manifests)
        os.makedirs(modules)
        result = audit.audit(manifests, modules, env={})
        assert isinstance(result, dict)


def test_audit_does_not_raise_when_modules_dir_missing():
    """If the modules dir is absent, the audit must still produce a summary."""
    with tempfile.TemporaryDirectory() as tmp:
        manifests = os.path.join(tmp, "manifests")
        os.makedirs(manifests)
        result = audit.audit(manifests, os.path.join(tmp, "nope"), env={})
        assert "summary" in result


def test_audit_writes_warnings_to_stderr_when_emit_to_stderr_true():
    with tempfile.TemporaryDirectory() as tmp:
        manifests, modules = _make_repo(
            tmp, [("foo", "# stub", ["NEEDED_TOKEN"])]
        )
        buf = io.StringIO()
        with redirect_stderr(buf):
            audit.audit(manifests, modules, env={}, emit_to_stderr=True)
        out = buf.getvalue()
        assert "NEEDED_TOKEN" in out


def test_audit_does_not_write_to_stderr_by_default():
    with tempfile.TemporaryDirectory() as tmp:
        manifests, modules = _make_repo(
            tmp, [("foo", "# stub", ["NEEDED_TOKEN"])]
        )
        buf = io.StringIO()
        with redirect_stderr(buf):
            audit.audit(manifests, modules, env={})
        assert buf.getvalue() == ""


def test_audit_uses_os_environ_when_env_not_supplied():
    """If env=None, audit reads from os.environ — so a probe set there
    is NOT reported as required-but-unconfigured. (declared-not-used
    drift can still fire on the stub source; that's a separate class.)"""
    with tempfile.TemporaryDirectory() as tmp:
        manifests, modules = _make_repo(
            tmp, [("foo", "# stub", ["AUDIT_TEST_PROBE"])]
        )
        os.environ["AUDIT_TEST_PROBE"] = "set"
        try:
            result = audit.audit(manifests, modules)  # no env=
            assert result["by_utility"]["foo"]["missing_env"] == [], (
                "probe is set in os.environ; should not be reported missing"
            )
        finally:
            del os.environ["AUDIT_TEST_PROBE"]


# ── runner ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_load_manifest_valid_returns_dict,
        test_load_manifest_invalid_json_returns_none,
        test_load_manifest_missing_file_returns_none,
        test_check_env_loadable_all_required_set,
        test_check_env_loadable_required_missing,
        test_check_env_loadable_required_empty_string_counts_as_missing,
        test_check_env_loadable_optional_unset_does_not_warn,
        test_check_env_loadable_handles_manifest_without_env,
        test_scope_drift_clean_when_source_uses_only_declared_env,
        test_scope_drift_flags_env_used_but_not_declared,
        test_scope_drift_flags_env_declared_but_not_used,
        test_scope_drift_recognizes_os_getenv_form,
        test_scope_drift_ignores_local_variable_named_like_env_var,
        test_index_diff_clean_when_modules_match_manifests,
        test_index_diff_reports_module_without_manifest,
        test_index_diff_reports_manifest_without_module,
        test_index_diff_ignores_dunder_and_tests_dir,
        test_audit_returns_dict_with_summary_and_warnings_keys,
        test_audit_summary_reports_audited_count,
        test_audit_flags_unconfigured_required_env,
        test_audit_flags_scope_drift,
        test_audit_flags_index_drift,
        test_audit_does_not_raise_on_empty_manifest_dir,
        test_audit_does_not_raise_when_modules_dir_missing,
        test_audit_writes_warnings_to_stderr_when_emit_to_stderr_true,
        test_audit_does_not_write_to_stderr_by_default,
        test_audit_uses_os_environ_when_env_not_supplied,
    ]

    passed = 0
    failed = 0
    errors = []
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((t.__name__, e))
            import traceback
            print(f"FAIL: {t.__name__}")
            traceback.print_exc()

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if errors:
        print()
        print("Failed tests:")
        for name, err in errors:
            print(f"  - {name}: {err}")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)
