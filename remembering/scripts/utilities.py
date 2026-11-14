import io
import json
import os
import re
import sys
import tarfile
import urllib.request

UTIL_DIR = os.environ.get("MUNINN_UTIL_DIR", os.path.join(os.path.expanduser("~"), "muninn_utils"))
# Manifests sit beside UTIL_DIR. fetch_muninn_utils() extracts them at boot
# from the same tarball; remembering.scripts.audit reads from here.
MANIFEST_DIR = os.environ.get("MUNINN_MANIFEST_DIR", os.path.join(os.path.dirname(UTIL_DIR), "manifests"))
CODE_START = "<" + "<" + "<PYTHON>" + ">" + ">"
CODE_END = "<" + "<" + "<END>" + ">" + ">"

# muninn_utils source-of-truth lives in oaustegard/muninn-utilities (public).
# Turso `utility-code` memories were the previous source; they are now archived
# (priority=-1) and retained only as forensic backup. See memories `0d63ed4f`
# (migration decision) and `9a61ecc8` (archive action record).
MUNINN_UTILS_REPO = os.environ.get("MUNINN_UTILS_REPO", "oaustegard/muninn-utilities")
MUNINN_UTILS_BRANCH = os.environ.get("MUNINN_UTILS_BRANCH", "main")
# Where boot.sh has already sideloaded the whole repo, through whichever of its
# three transports worked. fetch_muninn_utils() reads that tree in preference to
# the network: its own fetch goes straight to codeload with no auth, which the
# egress proxy intercepts in Cowork and scheduled-runner sessions, and it then
# returned an empty materialization with nothing in `failed` (2026-09-19).
MUNINN_UTILS_SRC = os.environ.get("MUNINN_UTILS_SRC", "/home/claude/muninn-utilities")
MUNINN_UTILS_SUBDIR = "muninn_utils"
USE_WHEN_FILE = "use_when.json"

# Valid utility names: alphanumeric, underscore, hyphen only
_VALID_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]*$')


# Manifest extraction. Names must match _VALID_NAME_RE plus a `.` for the
# extension; extracted-path realpath must be within MANIFEST_DIR.
_VALID_MANIFEST_DIR_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]*$')
_VALID_MANIFEST_FILE_RE = re.compile(r'^[A-Za-z0-9._-]+\.(json|md)$')


def _extract_manifest_member(tf, member, subdir: str, fname: str) -> None:
    """Write a single manifest file from the tarball into MANIFEST_DIR/<subdir>/.

    Path-safe: rejects `..`, absolute paths, and any resolution outside
    MANIFEST_DIR. Best-effort — silently skips on any error.
    """
    if not _VALID_MANIFEST_DIR_RE.match(subdir):
        return
    if not _VALID_MANIFEST_FILE_RE.match(fname):
        return

    target_dir = os.path.join(MANIFEST_DIR, subdir)
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, fname)

    manifest_realpath = os.path.realpath(MANIFEST_DIR) + os.sep
    resolved = os.path.realpath(target_path)
    if not resolved.startswith(manifest_realpath):
        return

    try:
        fileobj = tf.extractfile(member)
        if fileobj is None:
            return
        with open(target_path, "wb") as f:
            f.write(fileobj.read())
    except Exception:
        pass


# @lat: [[infrastructure#Utility Materialization]]
def install_utilities() -> dict:
    """
    Materialize utility-code memories to disk. LEGACY — boot() no longer calls
    this. Kept for any caller that still depends on memory-based materialization
    (e.g. one-off recovery, tests). New utilities should land in the
    oaustegard/muninn-utilities repo, not memory.

    Returns:
        Dict mapping utility names to {"path": file_path, "use_when": str|None}
    """
    from .memory import recall

    os.makedirs(UTIL_DIR, exist_ok=True)
    init_path = os.path.join(UTIL_DIR, "__init__.py")
    if not os.path.exists(init_path):
        open(init_path, 'w').close()

    parent = os.path.dirname(UTIL_DIR)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    results = recall(tags=["utility-code"], n=50)
    installed = {}

    for mem in results:
        content = mem.get("summary", "")
        if not content.startswith("NAME:"):
            continue
        name = content.split("\n")[0].replace("NAME:", "").strip()

        # Sanitize name: reject path separators, traversal, and invalid chars
        if not _VALID_NAME_RE.match(name):
            continue
        name = os.path.basename(name)  # Belt-and-suspenders

        if CODE_START not in content:
            continue
        code = content.split(CODE_START, 1)[1].split(CODE_END, 1)[0].strip()

        # Parse USE WHEN: from header (between PURPOSE: and DEPS:)
        use_when = None
        for line in content.split("\n"):
            if line.startswith("USE WHEN:"):
                use_when = line.replace("USE WHEN:", "").strip()
                break

        file_path = os.path.join(UTIL_DIR, f"{name}.py")
        # Final check: resolved path must be within UTIL_DIR
        resolved = os.path.realpath(file_path)
        if not resolved.startswith(os.path.realpath(UTIL_DIR) + os.sep):
            continue
        with open(file_path, 'w') as f:
            f.write(code + "\n")
        installed[name] = {"path": file_path, "use_when": use_when}

    return installed


def _materialize_from_local(result: dict) -> bool:
    """Copy muninn_utils/*.py + manifests/ from MUNINN_UTILS_SRC into UTIL_DIR.

    Returns True when at least one module was written, so the caller can fall
    through to the network fetch when the sideloaded tree is absent or partial.
    Applies the same name and containment checks as the tarball path — the
    source is a local clone, but the destination guarantees are the same.
    """
    src_utils = os.path.join(MUNINN_UTILS_SRC, MUNINN_UTILS_SUBDIR)
    if not os.path.isdir(src_utils):
        return False

    util_realpath = os.path.realpath(UTIL_DIR) + os.sep
    wrote = 0
    for name in sorted(os.listdir(src_utils)):
        src = os.path.join(src_utils, name)
        if not os.path.isfile(src):
            continue

        if name == USE_WHEN_FILE:
            try:
                with open(src, "r") as f:
                    result["use_when"] = json.load(f)
            except Exception:
                pass  # malformed use_when is non-fatal, same as the tar path
            continue

        if not name.endswith(".py"):
            continue
        if not _VALID_NAME_RE.match(name[:-3]):
            continue

        target = os.path.join(UTIL_DIR, name)
        if not os.path.realpath(target).startswith(util_realpath):
            continue
        try:
            with open(src, "rb") as rf, open(target, "wb") as wf:
                wf.write(rf.read())
            result["fetched"].append(name)
            wrote += 1
        except Exception:
            result["failed"].append(name)

    src_manifests = os.path.join(MUNINN_UTILS_SRC, "manifests")
    if os.path.isdir(src_manifests):
        manifest_realpath = os.path.realpath(MANIFEST_DIR) + os.sep
        for subdir in sorted(os.listdir(src_manifests)):
            sub = os.path.join(src_manifests, subdir)
            if not os.path.isdir(sub) or not _VALID_MANIFEST_DIR_RE.match(subdir):
                continue
            for fname in sorted(os.listdir(sub)):
                if not _VALID_MANIFEST_FILE_RE.match(fname):
                    continue
                target_dir = os.path.join(MANIFEST_DIR, subdir)
                os.makedirs(target_dir, exist_ok=True)
                target_path = os.path.join(target_dir, fname)
                if not os.path.realpath(target_path).startswith(manifest_realpath):
                    continue
                try:
                    with open(os.path.join(sub, fname), "rb") as rf, \
                            open(target_path, "wb") as wf:
                        wf.write(rf.read())
                except Exception:
                    pass  # best-effort, same as _extract_manifest_member

    return wrote > 0


# @lat: [[infrastructure#Utility Materialization]]
def fetch_muninn_utils() -> dict:
    """
    Pull canonical muninn_utils/*.py and use_when.json from
    oaustegard/muninn-utilities. This is the sole source of truth for utility
    code and discoverability metadata at boot.

    Reads MUNINN_UTILS_SRC first — the tree boot.sh already sideloaded through a
    transport that works here — and only falls back to a codeload tarball, which
    needs no auth but is intercepted in some session types. Skips tests/ subdir;
    only top-level *.py land in UTIL_DIR. use_when.json is parsed in-memory (not
    written to disk).

    Returns:
        Dict with keys:
        - fetched:  list[str] — names of .py files written
        - failed:   list[str] — names that errored during write
        - use_when: dict[str, str] — utility name → trigger description (parsed
                    from use_when.json in the repo; empty if absent or invalid)
        - source:   "local" | "codeload" | "none" — where the code came from.
                    "none" means nothing was materialized, which the manifest
                    audit reports as NOT AUDITED rather than as a passing zero.
    """
    result = {"fetched": [], "failed": [], "use_when": {}}

    os.makedirs(UTIL_DIR, exist_ok=True)
    init_path = os.path.join(UTIL_DIR, "__init__.py")
    if not os.path.exists(init_path):
        open(init_path, "w").close()

    parent = os.path.dirname(UTIL_DIR)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    if _materialize_from_local(result):
        result["source"] = "local"
        return result

    url = f"https://codeload.github.com/{MUNINN_UTILS_REPO}/tar.gz/{MUNINN_UTILS_BRANCH}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            raw = resp.read()
    except Exception:
        result["source"] = "none"
        return result
    result["source"] = "codeload"

    util_realpath = os.path.realpath(UTIL_DIR) + os.sep

    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                # Tarball paths:
                #   <repo>-<sha>/muninn_utils/<name>{.py,.json}    (utilities)
                #   <repo>-<sha>/manifests/<utility>/<file>        (install manifests, 4-deep)
                parts = member.name.split("/")

                # Manifests: 4 segments, second is "manifests".
                if len(parts) == 4 and parts[1] == "manifests":
                    _extract_manifest_member(tf, member, parts[2], parts[3])
                    continue

                # Utilities: 3 segments, second is muninn_utils/.
                if len(parts) != 3 or parts[1] != MUNINN_UTILS_SUBDIR:
                    continue
                name = parts[2]

                # use_when.json — parse in-memory, do not write to disk
                if name == USE_WHEN_FILE:
                    try:
                        fileobj = tf.extractfile(member)
                        if fileobj is not None:
                            result["use_when"] = json.loads(
                                fileobj.read().decode("utf-8")
                            )
                    except Exception:
                        pass  # malformed manifest is non-fatal
                    continue

                if not name.endswith(".py"):
                    continue
                stem = name[:-3]
                # __init__.py is the one allowed exception to the name regex
                if stem != "__init__" and not _VALID_NAME_RE.match(stem):
                    continue

                file_path = os.path.join(UTIL_DIR, name)
                # Final guard: resolved path must be within UTIL_DIR
                resolved = os.path.realpath(file_path)
                if not resolved.startswith(util_realpath):
                    result["failed"].append(name)
                    continue

                try:
                    fileobj = tf.extractfile(member)
                    if fileobj is None:
                        result["failed"].append(name)
                        continue
                    content = fileobj.read().decode("utf-8")
                    with open(file_path, "w") as f:
                        f.write(content)
                    result["fetched"].append(name)
                except Exception:
                    result["failed"].append(name)
    except Exception:
        # An unreadable archive materialized nothing, so `source` must not keep
        # claiming codeload — the whole point of the field is that a caller can
        # tell an empty materialization from a populated one.
        result["source"] = "none"
        return result

    if not result["fetched"]:
        result["source"] = "none"
    return result
