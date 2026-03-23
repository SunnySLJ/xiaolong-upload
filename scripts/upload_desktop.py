#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键上传桌面视频 - 支持抖音/快手/视频号/小红书
用法: python upload_desktop.py [--platform kuaishou] [视频路径]
默认: 桌面 3.mp4, 自动生成标题/文案/标签
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from upload import upload
from common.utils import gen_desktop_content

_PLATFORM_CONFIG = {
    "douyin": {"title_max": 30, "tags_max": 99, "default_tags": ["生活记录", "日常分享", "美好时光", "vlog"]},
    "kuaishou": {"title_max": 15, "tags_max": 4, "default_tags": ["生活记录", "日常分享", "美好时光", "vlog"]},
    "shipinhao": {"title_max": 64, "tags_max": 10, "default_tags": ["生活记录", "日常分享", "美好时光", "vlog", "小确幸"]},
    "xiaohongshu": {"title_max": 20, "tags_max": 5, "default_tags": ["生活记录", "日常分享", "美好时光", "vlog", "小确幸"]},
}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="一键上传桌面视频")
    parser.add_argument("--platform", "-p", default="kuaishou", choices=list(_PLATFORM_CONFIG), help="目标平台")
    parser.add_argument("video_path", nargs="?", default=str(Path.home() / "Desktop" / "3.mp4"), help="视频路径")
    args = parser.parse_args()

    path = Path(args.video_path)
    if not path.exists():
        print(f"❌ 视频不存在: {path}")
        sys.exit(1)

    cfg = _PLATFORM_CONFIG[args.platform]
    title, description, tags = gen_desktop_content(
        str(path),
        title_max=cfg["title_max"],
        tags_max=cfg["tags_max"],
        default_tags=cfg["default_tags"],
    )
    title = title[: cfg["title_max"]]
    tags = tags[: cfg["tags_max"]]

    print("📝 生成内容:")
    print(f"   标题: {title}")
    print(f"   文案: {description}")
    print(f"   标签: {', '.join(tags)}")
    print()

    ok = upload(
        platform=args.platform,
        video_path=str(path.resolve()),
        title=title,
        description=description,
        tags=tags,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
