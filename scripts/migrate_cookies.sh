#!/bin/bash
# 将旧版 cookies 迁移到统一 cookies/ 目录
# 若 platforms/*/cookies 存在且 cookies/<平台> 为空，则复制过去
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COOKIES="$ROOT/cookies"
PLATFORMS="$ROOT/platforms"

mkdir -p "$COOKIES"/{douyin,kuaishou,shipinhao,xiaohongshu}

for old in "$PLATFORMS/douyin_upload/cookies" "$PLATFORMS/ks_upload/cookies" \
           "$PLATFORMS/shipinhao_upload/cookies" "$PLATFORMS/xhs_upload/cookies"; do
  case "$old" in
    *douyin*) dest="$COOKIES/douyin" ;;
    *ks_*)    dest="$COOKIES/kuaishou" ;;
    *shipinhao*) dest="$COOKIES/shipinhao" ;;
    *xhs_*)   dest="$COOKIES/xiaohongshu" ;;
    *) continue ;;
  esac
  if [ -d "$old" ] && [ "$(ls -A "$old" 2>/dev/null)" ]; then
    if [ -z "$(ls -A "$dest" 2>/dev/null)" ]; then
      echo "迁移: $old -> $dest"
      cp -a "$old"/* "$dest"/ 2>/dev/null || cp -r "$old"/* "$dest"/
    fi
  fi
done
echo "✓ cookies 迁移完成"
