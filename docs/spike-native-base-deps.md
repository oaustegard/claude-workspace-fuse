# Spike: native install of the light base deps (vs. the GitHub-Releases layer path)

**Branch:** `claude/spike-native-base-deps` · **Opened:** 2026-07-07 · **Status:** experiment, not merged

## The question

The container-layer system caches every layer as a tarball in GitHub Releases
(`oaustegard/claude-container-layers`) and restores it at boot. That is the
*same* `codeload` / GitHub-proxy surface that **cold-start-degrades** — on a
fresh session the spokes are out of scope until the first-turn `add_repo`, so
layer restore 403s and boot comes up without its deps until recovery runs.

For the **heavy** layers (`scientific` ~55MB, `torch-cpu`, `julia-sr` ~1GB) the
tarball path earns that coupling: per-layer cache keys, dodging the ~5-minute
setup-script budget, and not rebuilding a 1GB Julia precompile every session.

For the **light always-on slice** it buys nothing:

| Dep | Real source | GitHub-scoped? |
|---|---|---|
| `httpx`, `libsql-experimental` | PyPI | No — `pypi.org` / `files.pythonhosted.org` are in the CCotw **Trusted** allowlist |
| `fusepy` | PyPI | No |
| `libfuse2`, `fusermount` | Ubuntu apt | No — apt repos are allowlisted |
| env-source shim | filesystem write | No network at all |
| `gh` CLI | (vestigial) | CLAUDE.md: "not used anywhere in this repo's operational paths" |

None of the light deps *need* GitHub. Routing them through the Releases cache
only inherits its cold-start fragility.

## What this spike changes

- **`scripts/install-base-deps.sh`** (new) — idempotent installer for the light
  slice, from PyPI + apt only. Fast no-op when the deps are already on disk.
- **`boot-ccotw.sh`** — calls `_ensure_base_deps` right after the network wait,
  **before** the layer compose, in both the cold and cached-marker paths.
- **`.claude/container-layers.json`** — drops `base` and `fuse`; the manifest is
  now `["scientific", "torch-cpu"]`. The heavy layers stay on the layer system.
- `layers/Containerfile` and `layers/Containerfile.fuse` are **left in place**
  (unused by the manifest) so reverting is a one-line manifest change.

The net effect: the light deps install from allowlisted registries that a cold
start cannot scope out, and only the heavy layers depend on the GitHub path.

## How to compare

Boot a fresh session on this branch and on `main`, and compare:

1. **Cold-start reliability** — does `python3 -c "import httpx, fuse"` succeed at
   tick 0 on this branch even when the container-layer skill fetch 403s? On
   `main` those come from the `base`/`fuse` layers, which 403 with everything
   else.
2. **Boot telemetry** — the new `base_deps` `_tmark`. On a warm cache it should
   be a sub-second no-op; on a cold PyPI install, a few seconds.
3. **memfs** — `/mnt/muninn` should mount without needing the fuse-layer cache
   or the recovery script's apt fallback.

Note this does **not** remove the need for the first-turn `add_repo` recovery:
skills, `remembering`, and the memfs corpus still come from the spokes via
`codeload`. This spike only decouples the *dependency* slice from that path.

## Revert

Restore the manifest to `["base", "scientific", "torch-cpu", "fuse"]` and drop
the `_ensure_base_deps` calls from `boot-ccotw.sh`. The layer Containerfiles were
never deleted.
