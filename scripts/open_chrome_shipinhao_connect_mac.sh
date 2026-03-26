#!/usr/bin/env bash
set -euo pipefail

# Start a dedicated Chrome for WeChat 视频号 (Channels) connect mode (CDP).
# Port: 9226 (matches scripts/upload_shipinhao_connect.ps1 and docs/LOGIN_FLOW.md)

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${CDP_DEBUG_PORT:-9226}"
URL="https://channels.weixin.qq.com/platform/post/create"

CHROME_PATH="${LOCAL_CHROME_PATH:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
PROFILE_DIR="${CHROME_USER_DATA_DIR:-$PROJECT_ROOT/cookies/chrome_connect_sph}"

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

