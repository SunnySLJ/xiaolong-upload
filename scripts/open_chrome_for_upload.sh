#!/usr/bin/env bash
# Mac/Linux: connect 模式需先运行此脚本，打开带 CDP 的 Chrome
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROFILE_DIR="$PROJECT_ROOT/cookies/chrome_connect"
CHROME="${LOCAL_CHROME_PATH}"
if [ -z "$CHROME" ]; then
  if [ "$(uname)" = "Darwin" ]; then
    CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  else
    CHROME="google-chrome"
  fi
fi

mkdir -p "$PROFILE_DIR"
echo "📱 启动上传用 Chrome（connect 模式）"
exec "$CHROME" \
  --remote-debugging-port=9222 \
  --user-data-dir="$PROFILE_DIR" \
  "https://creator.douyin.com/creator-micro/content/upload"
