#!/usr/bin/env bash
set -euo pipefail

# Start a dedicated Chrome for Douyin connect mode (CDP).
# Port: 9224 (matches scripts/upload_douyin_connect.ps1 and docs/LOGIN_FLOW.md)

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${CDP_DEBUG_PORT:-9224}"
URL="https://creator.douyin.com/creator-micro/content/upload"

CHROME_PATH="${LOCAL_CHROME_PATH:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
PROFILE_DIR="${CHROME_USER_DATA_DIR:-$PROJECT_ROOT/cookies/chrome_connect_dy}"

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

