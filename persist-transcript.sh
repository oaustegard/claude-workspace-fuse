#!/bin/bash
# Stop hook: persist session transcript to GitHub Releases
# Reads hook JSON from stdin
set -e

input=$(cat)

stop_hook_active=$(echo "$input" | jq -r '.stop_hook_active // false')
[ "$stop_hook_active" = "true" ] && exit 0

REPO="${TRANSCRIPT_REPO:-oaustegard/claude-container-layers}"
TOKEN="${GH_TOKEN:-}"
[ -z "$TOKEN" ] && exit 0

# Find transcript JSONL — walk the projects dir
TRANSCRIPT_DIR="$HOME/.claude/projects"
TRANSCRIPT=$(find "$TRANSCRIPT_DIR" -name "*.jsonl" -newer /tmp/.workstation-booted 2>/dev/null | head -1)
[ -z "$TRANSCRIPT" ] && exit 0

SESSION_ID=$(basename "$TRANSCRIPT" .jsonl)
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
ARCHIVE="/tmp/_transcript_${SESSION_ID}.tar.gz"

# Tar just this session's transcript
tar -czf "$ARCHIVE" -C "$(dirname "$TRANSCRIPT")" "$(basename "$TRANSCRIPT")" 2>/dev/null

# Also build a rolling "latest" archive with all transcripts
LATEST_ARCHIVE="/tmp/_transcripts_latest.tar.gz"
tar -czf "$LATEST_ARCHIVE" -C "$HOME/.claude" projects/ 2>/dev/null

_gh_api() {
  local method="$1" endpoint="$2" data="$3"
  local url="https://api.github.com${endpoint}"
  if [ -n "$data" ]; then
    curl -sf -X "$method" \
      -H "Authorization: token $TOKEN" \
      -H "Accept: application/vnd.github+json" \
      -H "Content-Type: application/json" \
      -d "$data" "$url" 2>/dev/null
  else
    curl -sf -X "$method" \
      -H "Authorization: token $TOKEN" \
      -H "Accept: application/vnd.github+json" \
      "$url" 2>/dev/null
  fi
}

_upload_asset() {
  local upload_url="$1" filepath="$2" name="$3"
  upload_url="${upload_url%%\{*}?name=${name}"
  curl -sf -X POST \
    -H "Authorization: token $TOKEN" \
    -H "Content-Type: application/gzip" \
    --data-binary "@${filepath}" \
    "$upload_url" >/dev/null 2>&1
}

# ── Per-session archive ──
TAG="transcript-${TIMESTAMP}-${SESSION_ID:0:8}"
RELEASE=$(_gh_api POST "/repos/$REPO/releases" \
  "{\"tag_name\":\"$TAG\",\"name\":\"Session $TIMESTAMP\",\"body\":\"Auto-archived session transcript.\",\"prerelease\":true}")

if [ -n "$RELEASE" ]; then
  UPLOAD_URL=$(echo "$RELEASE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('upload_url',''))" 2>/dev/null)
  [ -n "$UPLOAD_URL" ] && _upload_asset "$UPLOAD_URL" "$ARCHIVE" "transcript.tar.gz"
fi

# ── Rolling "latest" archive (replace existing) ──
EXISTING=$(_gh_api GET "/repos/$REPO/releases/tags/transcripts-latest")
if [ -n "$EXISTING" ]; then
  EXISTING_ID=$(echo "$EXISTING" | python3 -c "import json,sys; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
  [ -n "$EXISTING_ID" ] && _gh_api DELETE "/repos/$REPO/releases/$EXISTING_ID" >/dev/null
fi

LATEST=$(_gh_api POST "/repos/$REPO/releases" \
  "{\"tag_name\":\"transcripts-latest\",\"name\":\"Latest Transcripts\",\"body\":\"Rolling archive of all session transcripts.\",\"prerelease\":true}")

if [ -n "$LATEST" ]; then
  UPLOAD_URL=$(echo "$LATEST" | python3 -c "import json,sys; print(json.load(sys.stdin).get('upload_url',''))" 2>/dev/null)
  [ -n "$UPLOAD_URL" ] && _upload_asset "$UPLOAD_URL" "$LATEST_ARCHIVE" "transcripts.tar.gz"
fi

rm -f "$ARCHIVE" "$LATEST_ARCHIVE"
exit 0
