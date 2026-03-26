#!/usr/bin/env bash
set -euo pipefail

# Start a dedicated Chrome for Xiaohongshu connect mode (CDP).
# Port: 9223 (matches scripts/upload_xiaohongshu_connect.ps1 and docs/LOGIN_FLOW.md)

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${CDP_DEBUG_PORT:-9223}"
URL="https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video"

CHROME_PATH="${LOCAL_CHROME_PATH:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
PROFILE_DIR="${CHROME_USER_DATA_DIR:-$PROJECT_ROOT/cookies/chrome_connect_xhs}"

mkdir -p "$PROFILE_DIR"

echo "Starting Chrome (port=$PORT)"
echo "Chrome: $CHROME_PATH"
echo "Profile: $PROFILE_DIR"
echo "URL: $URL"

"$CHROME_PATH" \
  --remote-debugging-port="$PORT" \
  --user-data-dir="$PROFILE_DIR" \
  --start-maximized \
  "$URL"

