#!/bin/bash
# Mac 双击运行 - 统一上传（使用根目录 .venv）
# 用法: 传入参数给 upload.py，如 -p kuaishou /path/video.mp4 "标题" "文案" "标签"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

ensure_venv() {
    if [ ! -d ".venv" ]; then
        echo "创建虚拟环境..."
        python3.12 -m venv .venv 2>/dev/null || python3 -m venv .venv
        .venv/bin/pip install -q -r requirements.txt
    fi
}
ensure_venv
.venv/bin/python upload.py "$@"
read -p "按回车键关闭..."
