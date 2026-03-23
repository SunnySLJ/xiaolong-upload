#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抖音上传 CLI - 兼容 Mac/Windows，供技能或命令行调用

用法:
  python upload_cli.py <视频路径> <标题> [文案] [标签1,标签2,...]
"""
import sys
import platform
from pathlib import Path

# 确保从项目根目录导入
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api import upload_to_douyin


def main():
    if len(sys.argv) < 3:
        print("用法: upload_cli.py <视频路径> <标题> [文案] [标签1,标签2,...]")
        print("示例: upload_cli.py /path/to/video.mp4 记录生活 美好的一天 vlog,日常")
        sys.exit(1)

    video_path = sys.argv[1]
    title = sys.argv[2]
    description = sys.argv[3] if len(sys.argv) > 3 else ""
    tags = sys.argv[4].split(",") if len(sys.argv) > 4 else []
    tags = [t.strip() for t in tags if t.strip()]

    ok = upload_to_douyin(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
