#!/usr/bin/env bash
set -euo pipefail

# Start a dedicated Chrome for Kuaishou connect mode (CDP).
# Port: 9225 (matches scripts/upload_kuaishou_connect.ps1 and docs/LOGIN_FLOW.md)

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${CDP_DEBUG_PORT:-9225}"
URL="https://cp.kuaishou.com/article/publish/video"

CHROME_PATH="${LOCAL_CHROME_PATH:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
PROFILE_DIR="${CHROME_USER_DATA_DIR:-$PROJECT_ROOT/cookies/chrome_connect_ks}"

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

