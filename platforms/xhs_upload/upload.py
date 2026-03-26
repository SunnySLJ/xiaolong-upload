#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书视频上传 - 统一入口（Mac / Windows 兼容）

用法：
  命令行: python upload.py <视频路径> <标题> [文案] [标签1,标签2,...]
  API:   from upload import upload; upload(video_path="...", title="...", description="...", tags=[...])
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

# 项目根加入 path
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
_ROOT = _PROJECT_ROOT.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from common.console import ensure_console_ready, safe_print

ensure_console_ready()

# Python 版本检查（nodriver 需 3.10+）
if sys.version_info < (3, 10):
    safe_print("错误: 需要 Python 3.10 及以上，当前: %s" % sys.version.split()[0])
    sys.exit(1)


def upload(
    video_path: str,
    title: str,
    description: str = "",
    tags: Optional[List[str]] = None,
    account_name: str = "default",
    handle_login: bool = True,
) -> bool:
    """
    上传视频到小红书

    :param video_path: 视频文件路径
    :param title: 标题（最多 20 字）
    :param description: 文案/描述
    :param tags: 标签列表，最多 5 个
    :param account_name: 账号名
    :param handle_login: 未登录时是否打开浏览器引导登录
    :return: 是否成功
    """
    from platforms.xhs_upload.api import upload_to_xiaohongshu

    tags = tags or []
    tags = [t.strip() for t in tags if t.strip()][:5]
    return upload_to_xiaohongshu(
        video_path=video_path,
        title=(title or "")[:20],
        description=description or "",
        tags=tags,
        account_name=account_name,
        handle_login=handle_login,
    )


def _main():
    import argparse

    parser = argparse.ArgumentParser(
        description="小红书视频上传（Mac/Windows 兼容）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python upload.py /path/to/video.mp4 "今日份快乐" "美好的一天 ✨" "生活记录,日常,vlog"
  python upload.py D:\\videos\\a.mp4 "标题" "文案" "标签1,标签2,标签3"

API 调用:
  from upload import upload
  upload(video_path="...", title="...", description="...", tags=["a","b"])
        """,
    )
    parser.add_argument("video_path", help="视频文件路径")
    parser.add_argument("title", help="标题（最多 20 字）")
    parser.add_argument("description", nargs="?", default="", help="文案/描述")
    parser.add_argument(
        "tags",
        nargs="?",
        default="",
        help="标签，逗号分隔，最多 5 个。如: 生活记录,日常,vlog",
    )
    parser.add_argument(
        "--account",
        default="default",
        help="账号名（默认: default）",
    )
    parser.add_argument(
        "--no-login",
        action="store_true",
        help="未登录时不自动打开浏览器",
    )
    args = parser.parse_args()

    tags_list = [t.strip() for t in args.tags.split(",") if t.strip()][:5]
    ok = upload(
        video_path=args.video_path,
        title=args.title,
        description=args.description,
        tags=tags_list,
        account_name=args.account,
        handle_login=not args.no_login,
    )
    sys.exit(0 if ok else 1)


def main():
    """CLI 入口"""
    _main()


if __name__ == "__main__":
    main()
