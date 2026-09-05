#!/bin/bash
# Muninn boot — sideload skills + utilities, load env, run boot().
#
# Sideload is DYNAMIC: it tracks each repo's main branch (not a pinned SHA) so
# changes land the next cold boot without a version bump. The trade is that main
# is fetched as-is, unreviewed; keep main deployable.
#
# THREE TRANSPORTS, in preference order (2026-07-30). Anthropic's session egress
# proxy intercepts codeload/api.github.com/github.com in some session types
# (Cowork, scheduled runners) and returns 403.
#
#   1. codeload tarball          — 1 request. Works in CCotw / Claude.ai project
#                                  sessions where codeload is not intercepted.
#   2. gh-api-proxy tarball      — 1 request. Works everywhere the worker is
#                                  reachable. Needs CF_GH_PROXY_KEY + GH_TOKEN.
#                                  gh-api-proxy follows the /tarball 302 to
#                                  codeload SERVER-SIDE, so we never touch a
#                                  blocked host. Authoritative, never CDN-stale.
#   3. raw + MANIFEST.txt        — N requests, one per file. No credentials, no
#                                  add_repo. Last resort: it is ~20x the requests
#                                  and subject to the CDN staleness below.
#
# ⚠️ RAW IS CDN-CACHED ON BRANCH REFS (~minutes), and the cache is NOT
# client-bustable — Cache-Control: no-cache, Pragma, and query-string busters all
# still serve the stale copy (measured 2026-07-29). A cold boot within a few
# minutes of a push to main can therefore sideload PRE-PUSH code, silently.
# Symptom: freshly committed fixes appear absent on disk. Tier 2 is immune —
# prefer it when iterating.
# Both REF vars accept a branch, tag, or full SHA (a SHA is never stale on raw).
set -e
CLAUDE_SKILLS_REF=${CLAUDE_SKILLS_REF:-main}
MUNINN_UTILS_REF=${MUNINN_UTILS_REF:-main}
RAW=https://raw.githubusercontent.com
PROXY=${GH_API_PROXY:-https://gh-api-proxy.austegard.workers.dev}

# This script reads no sibling files, so it does not need to know where it lives —
# which is what makes it mount-agnostic (/mnt/skills/user/muninn-boot on
# Claude.ai, /root/.claude/skills/muninn-boot in Cowork). Keep it that way; the
# moment it sources a sibling, add a BASH_SOURCE-based dir resolution.

# Project env files. Claude.ai mounts /mnt/project; Cowork does not (they are
# project docs there, and the session writes them here before calling this).
PROJECT_DIR=${MUNINN_PROJECT_DIR:-/mnt/project}

# Warm-container fast path. The project instruction is reinjected every message,
# so this script is invoked many times per conversation. The sentinel's lifetime
# is the container's: a recycled container lacks it and fetches fresh; a warm one
# exits here. skinny boot (BOOT_MODE set) always runs fully.
SENTINEL=/home/claude/.muninn-booted
if [ -z "$BOOT_MODE" ] \
   && [ -f "$SENTINEL" ] \
   && [ -d /home/claude/muninn-utilities/muninn_utils ]; then
  echo "warm boot: already fetched this container. rm $SENTINEL to re-pull main."
  exit 0
fi

cd /tmp

# ── sideload: tarball if reachable, else raw + MANIFEST ───────────────────────
tarball_ok() {
  # A real tarball is gzip. The interception returns JSON with a 200-ish body,
  # so check the magic bytes, not just curl's exit status.
  [ -s "$1" ] && [ "$(head -c2 "$1" | od -An -tx1 | tr -d ' \n')" = "1f8b" ]
}

unpack() {  # tgz destdir  — strip the single top-level dir the archive wraps
  local tgz=$1 dest=$2 tmp
  tmp=$(mktemp -d) || return 1
  tar -xzf "$tgz" -C "$tmp" --strip-components=1 || { rm -rf "$tmp"; return 1; }
  mkdir -p "$dest"
  cp -r "$tmp"/. "$dest"/ || { rm -rf "$tmp"; return 1; }
  rm -rf "$tmp"
}

fetch_tarball() {  # repo ref destdir  — tier 1: codeload direct
  local repo=$1 ref=$2 dest=$3 tgz=/tmp/$(basename "$repo").tar.gz
  curl -sL "https://codeload.github.com/$repo/tar.gz/$ref" -o "$tgz" || return 1
  tarball_ok "$tgz" || return 1
  unpack "$tgz" "$dest"
}

fetch_via_proxy() {  # repo ref destdir  — tier 2: gh-api-proxy /tarball
  local repo=$1 ref=$2 dest=$3 tgz=/tmp/$(basename "$repo")-proxy.tar.gz
  [ -n "${CF_GH_PROXY_KEY:-}" ] && [ -n "${GH_TOKEN:-}" ] || return 1
  [ "${GH_TOKEN}" != "proxy-injected" ] || return 1
  # -L: the worker follows the codeload 302 itself, but keep -L for any
  # api.github.com-side redirect it hands back.
  curl -sL "$PROXY/repos/$repo/tarball/$ref" -o "$tgz" \
    -H "X-Proxy-Key: $CF_GH_PROXY_KEY" \
    -H "Authorization: Bearer $GH_TOKEN" \
    -H "User-Agent: muninn-raven" \
    -H "Accept: application/vnd.github+json" || return 1
  tarball_ok "$tgz" || return 1
  unpack "$tgz" "$dest"
}

fetch_via_manifest() {  # repo ref destdir manifest-path
  local repo=$1 ref=$2 dest=$3 man=$4 n=0 want=0
  if ! curl -sf "$RAW/$repo/$ref/$man" -o /tmp/MANIFEST.txt; then
    echo "  ERROR: $man not found at $repo@$ref."
    echo "  The raw fallback is manifest-driven and cannot list directories, so a"
    echo "  ref without a manifest cannot be sideloaded this way. Check that \$ref"
    echo "  exists and carries $man (branches deleted on merge 404 here)."
    return 1
  fi
  grep -v '^#' /tmp/MANIFEST.txt | grep -v '^[[:space:]]*$' > /tmp/manifest.clean
  want=$(wc -l < /tmp/manifest.clean)
  while read -r p; do
    mkdir -p "$dest/$(dirname "$p")"
    curl -sf "$RAW/$repo/$ref/$p" -o "$dest/$p" && n=$((n+1))
  done < /tmp/manifest.clean
  echo "  raw sideload: $n/$want files from $repo@$ref"
  # Partial fetch is worse than none — it boots into a half-populated package.
  [ "$n" -eq "$want" ] || { echo "  ERROR: $((want-n)) file(s) failed to fetch"; return 1; }
}

# ── env FIRST: tier 2 needs GH_TOKEN, and the proxy key needs TURSO_TOKEN ─────
# `set -a` + source, so these export. NOTE: the container presets
# GH_TOKEN=proxy-injected, a placeholder that is truthy but useless to GitHub —
# sourcing must OVERWRITE it, never setdefault. See muninn_utils.gh_proxy.
set -a
. "$PROJECT_DIR/Turso.env" 2>/dev/null
. "$PROJECT_DIR/GitHub.env" 2>/dev/null
set +a

if [ "${GH_TOKEN:-}" = "proxy-injected" ]; then
  echo "WARN: GH_TOKEN is still the container placeholder — $PROJECT_DIR/GitHub.env" \
       "missing or unreadable. GitHub calls will 401."
fi

# ── boot-payload fire instrumentation (#84) ──────────────────────────────────
# config_get() increments fire_count/last_fired for boot_load=1 keys when this
# is set. Written in boot_ledger v0.1.0 as opt-in and consequently never once
# switched on: 54 boot-loaded entries, SUM(fire_count)=0, last_fired=NULL as of
# 2026-08-05. So the ledger has been ranking the entire boot payload on its
# memory-corpus PROXY — "did this entry's subject show up in logged work" —
# while the exact counter sat dark. Default it on; a measurement window only
# accumulates if sessions actually record. Cost is one best-effort, self-
# silencing UPDATE per config_get on a boot-loaded key. Opt out with
# MUNINN_INSTRUMENT_FIRES=0.
# Exporting alone is not enough: this shell dies when boot.sh returns, and
# boot() itself reads config by bulk SELECT rather than config_get, so it would
# count nothing anyway. Every LATER bash call is a fresh shell that sources
# Turso.env as its standing preamble — so the flag has to live in that file to
# survive. Appended idempotently; this is what the project-instructions prose
# used to do by hand, which meant a session that skipped the step measured
# nothing and looked identical to one that measured zero.
case "${MUNINN_INSTRUMENT_FIRES:-1}" in
  0|false|no) unset MUNINN_INSTRUMENT_FIRES ;;
  *) export MUNINN_INSTRUMENT_FIRES=1
     if [ -w "$PROJECT_DIR/Turso.env" ] &&
        ! grep -q '^MUNINN_INSTRUMENT_FIRES=' "$PROJECT_DIR/Turso.env" 2>/dev/null; then
       echo 'MUNINN_INSTRUMENT_FIRES=1' >> "$PROJECT_DIR/Turso.env"
     fi ;;
esac

# The proxy key lives in Turso ops config, not an env file. Fetch it directly —
# we cannot use scripts.config_get yet, since that is what we are sideloading.
# Best-effort: without it tier 2 is skipped and we fall through to tier 3.
if [ -z "${CF_GH_PROXY_KEY:-}" ] && [ -n "${TURSO_TOKEN:-}" ] && [ -n "${TURSO_URL:-}" ]; then
  CF_GH_PROXY_KEY=$(python3 - <<'PY' 2>/dev/null || true
import json, os, re, urllib.request
url = f"https://{os.environ['TURSO_URL']}/v2/pipeline"
payload = json.dumps({"requests": [
    {"type": "execute", "stmt": {
        "sql": "select value from config where key = 'cf-gh-proxy-key'"}},
    {"type": "close"}]}).encode()
req = urllib.request.Request(url, data=payload, headers={
    "Authorization": "Bearer " + os.environ["TURSO_TOKEN"],
    "Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=20) as r:
    doc = json.load(r)
rows = doc["results"][0]["response"]["result"]["rows"]
raw = rows[0][0]["value"] if rows else ""
# The ops value carries usage docs after the key; take the first key-shaped line.
for line in raw.splitlines():
    line = line.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{20,}", line):
        print(line)
        break
PY
)
  export CF_GH_PROXY_KEY
fi

# ── sideload: codeload -> gh-api-proxy tarball -> raw+MANIFEST ────────────────
sideload() {  # repo ref destdir manifest-path-or-empty
  local repo=$1 ref=$2 dest=$3 man=$4
  if fetch_tarball "$repo" "$ref" "$dest"; then
    echo "  codeload tarball ok (1 request)"; return 0
  fi
  if fetch_via_proxy "$repo" "$ref" "$dest"; then
    echo "  gh-api-proxy tarball ok (1 request)"; return 0
  fi
  if [ -n "$man" ]; then
    echo "  both tarball paths unavailable -> raw + $man (one request per file)"
    fetch_via_manifest "$repo" "$ref" "$dest" "$man" && return 0
  fi
  return 1
}

echo "sideloading muninn-utilities..."
sideload oaustegard/muninn-utilities "$MUNINN_UTILS_REF" \
  /home/claude/muninn-utilities remembering/MANIFEST.txt

echo "sideloading claude-skills..."
mkdir -p /mnt/skills/user
# No manifest in this repo, so tiers 1-2 only.
if sideload oaustegard/claude-skills "$CLAUDE_SKILLS_REF" /mnt/skills/user ""; then
  :
else
  echo "  codeload intercepted -> skipping general skills (raw has no listing;"
  echo "  plugin-synced copies under /root/.claude/plugins/synced are used instead)"
fi

# ── python path ──────────────────────────────────────────────────────────────
# Resolve site-packages at runtime; it is 3.12/dist-packages on Claude.ai and
# 3.11/site-packages in Cowork.
PTH=$(python3 - <<'PY'
import site, sys, os
cands = [p for p in sys.path if p.endswith(('site-packages', 'dist-packages'))]
for c in (site.getusersitepackages(),) if hasattr(site, 'getusersitepackages') else ():
    if c not in cands:
        cands.insert(0, c)
writable = [c for c in cands if os.path.isdir(c) and os.access(c, os.W_OK)]
target = (writable or cands)[0]
os.makedirs(target, exist_ok=True)
print(os.path.join(target, 'muninn-remembering.pth'))
PY
)
HOMEDIR=$(python3 -c 'import os; print(os.path.expanduser("~"))')
printf '%s\n' \
  /home/claude/muninn-utilities/remembering \
  /home/claude/muninn-utilities \
  "$HOMEDIR" > "$PTH"
for d in /mnt/skills/user/*/scripts/; do
  ls "$d"*.py >/dev/null 2>&1 && echo "$d" >> "$PTH"
done
echo "python path: $PTH"

python3 << 'PYBOOT'
import os
from scripts import boot
print(boot(mode=os.environ.get('BOOT_MODE')))
PYBOOT

touch "$SENTINEL"   # last line, only on success
