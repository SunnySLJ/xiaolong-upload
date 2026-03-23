#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开发调试入口：修改下方参数后直接运行
用法: python run_upload.py [--platform douyin|kuaishou|shipinhao|xiaohongshu]
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ========== 修改以下参数 ==========
VIDEO_FILE = "/Users/h/Desktop/3.mp4"
TITLE = "记录生活中的小确幸"
DESCRIPTION = "每一个平凡的日子都藏着惊喜 ✨"
TAGS = ["生活记录", "日常分享", "美好时光"]
ACCOUNT_NAME = "default"
PLATFORM = "kuaishou"  # douyin | kuaishou | shipinhao | xiaohongshu
# =================================


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--platform" and len(sys.argv) > 2:
        platform = sys.argv[2].lower()
    else:
        platform = PLATFORM

    from upload import upload as do_upload

    # 按平台限制标题/标签长度
    title = TITLE
    tags = TAGS[:]
    if platform == "kuaishou":
        title, tags = title[:15], tags[:4]
    elif platform == "xiaohongshu":
        title, tags = title[:20], tags[:5]

    ok = do_upload(
        platform=platform,
        video_path=VIDEO_FILE,
        title=title,
        description=DESCRIPTION,
        tags=tags,
        account_name=ACCOUNT_NAME,
    )
    print("✅ 上传完成" if ok else "❌ 上传失败")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
