#!/usr/bin/env python3
"""Regenerate remembering/MANIFEST.txt from the repo's git tree.

MANIFEST.txt is the file list a raw.githubusercontent sideload walks. It exists
because:
  - codeload / api.github.com / github.com are intercepted by Anthropic's session
    egress proxy in some session types (Cowork, scheduled runners), so the tarball
    path is unavailable there; raw.githubusercontent is not intercepted.
  - raw offers no directory listing.
  - deriving the list by walking `from .x import` statements misses every runtime
    DATA file — scripts/defaults/*.json, scripts/tasks/*.md — which boot() and
    capabilities() load by path. Symptom: boot succeeds but the Task Routing block
    silently renders empty. Diagnosed 2026-07-29.

Run from a checkout:   python3 remembering/scripts/gen_manifest.py
Run against the API:   python3 remembering/scripts/gen_manifest.py --remote
"""
import argparse
import os
import sys

HEADER = """\
# Runtime file manifest for a raw.githubusercontent sideload.
# codeload/api.github.com are intercepted by Anthropic's session egress
# proxy in some session types (Cowork, scheduled runners); raw is not.
# raw has no directory listing, and an import-graph walk misses data
# files (defaults/*.json, tasks/*.md), so this list is the manifest.
# Regenerate: python3 remembering/scripts/gen_manifest.py
# Excludes tests/.
"""

# What a session actually LOADS, as opposed to what merely has a plausible
# extension. Selecting by extension alone pulled in CHANGELOG.md, README.md,
# _ARCH.md, references/*.md and migrations/* — 12 files no code path opens, each
# costing an HTTP round trip on the raw fallback. Fixed 2026-07-30.
INCLUDE = (
    'remembering/SKILL.md',              # skill descriptor, read when mounted
    'remembering/scripts/',              # boot + memory code, defaults/, tasks/
    'muninn_utils/',                     # utility package
)
EXCLUDE_DIRS = ('/tests/', '/migrations/', '/__pycache__/', 'remembering/references/')
EXCLUDE_EXACT = (
    'remembering/CHANGELOG.md',
    'remembering/README.md',
    'remembering/_ARCH.md',
    'remembering/.skillignore',
    'remembering/MANIFEST.txt',          # the manifest fetches itself first
)
SUFFIXES = ('.py', '.json', '.md')


def is_runtime(path: str) -> bool:
    if path in EXCLUDE_EXACT or any(d in path for d in EXCLUDE_DIRS):
        return False
    if not any(path == inc or path.startswith(inc) for inc in INCLUDE):
        return False
    return path.endswith(SUFFIXES)


def from_checkout(root: str) -> list:
    out = []
    roots = {inc.split('/')[0] for inc in INCLUDE}
    for prefix in roots:
        for dirpath, dirnames, filenames in os.walk(os.path.join(root, prefix)):
            dirnames[:] = [d for d in dirnames if d not in ('tests', '__pycache__')]
            for fn in filenames:
                rel = os.path.relpath(os.path.join(dirpath, fn), root)
                if is_runtime(rel):
                    out.append(rel)
    return sorted(out)


def from_remote() -> list:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
    from muninn_utils.gh_proxy import rest
    status, tree = rest('/repos/oaustegard/muninn-utilities/git/trees/main?recursive=1')
    if status != 200:
        sys.exit(f'tree fetch failed: HTTP {status}')
    return sorted(e['path'] for e in tree['tree']
                  if e['type'] == 'blob' and is_runtime(e['path']))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--remote', action='store_true',
                    help='read the tree from GitHub instead of the local checkout')
    ap.add_argument('--check', action='store_true',
                    help='exit 1 if MANIFEST.txt is stale (for CI)')
    a = ap.parse_args()

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
    paths = from_remote() if a.remote else from_checkout(root)
    body = HEADER + '\n'.join(paths) + '\n'
    dest = os.path.join(root, 'remembering/MANIFEST.txt')

    if a.check:
        current = open(dest).read() if os.path.exists(dest) else ''
        if current != body:
            have = {l for l in current.splitlines() if l and not l.startswith('#')}
            want = set(paths)
            for p in sorted(want - have):
                print('  missing from manifest:', p)
            for p in sorted(have - want):
                print('  stale in manifest:', p)
            sys.exit('MANIFEST.txt is stale — run gen_manifest.py')
        print(f'MANIFEST.txt current ({len(paths)} entries)')
        return

    with open(dest, 'w') as f:
        f.write(body)
    print(f'wrote {dest} ({len(paths)} entries)')


if __name__ == '__main__':
    main()
