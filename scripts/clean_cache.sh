#!/bin/bash
# 清理项目内所有 __pycache__ 和 .pyc（不含 .venv）
cd "$(dirname "$0")/.."
find . -type d -name "__pycache__" ! -path "*/.venv/*" 2>/dev/null | while read d; do rm -rf "$d"; done
find . -name "*.pyc" ! -path "*/.venv/*" -delete 2>/dev/null || true
echo "✓ 已清理 Python 缓存"
