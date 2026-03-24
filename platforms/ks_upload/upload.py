#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快手视频上传 - 统一入口（Mac / Windows 兼容）

用法：
  命令行: python upload.py <视频路径> <标题> [文案] [标签1,标签2,...]
  API:   from upload import upload; upload(video_path="...", title="...", description="...", tags=[...])
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 确保可导入 common（项目根目录）
_ROOT = _PROJECT_ROOT.parent.parent  # longxia_upload
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from common.console import ensure_console_ready, safe_print
from common.utils import extract_tags_from_description

ensure_console_ready()

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
    上传视频到快手

    :param video_path: 视频文件路径
    :param title: 标题（最多 15 字）
    :param description: 文案/描述
    :param tags: 标签列表，最多 4 个
    :param account_name: 账号名
    :param handle_login: 未登录时是否打开浏览器引导登录
    :return: 是否成功
    """
    from platforms.ks_upload.api import upload_to_kuaishou

    tags = [str(t).replace("#", "").strip() for t in (tags or []) if t][:4]
    description = description or ""
    # 未显式传 tags 时，从文案中提取 #xxx（快手最多 4 个）
    if not tags and "#" in description:
        description, tags = extract_tags_from_description(description, max_tags=4)
    return upload_to_kuaishou(
        video_path=video_path,
        title=(title or "")[:15],
        description=description,
        tags=tags,
        account_name=account_name,
        handle_login=handle_login,
    )


def _main():
    import argparse

    parser = argparse.ArgumentParser(
        description="快手视频上传（Mac/Windows 兼容）",
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
    parser.add_argument("title", help="标题（最多 15 字）")
    parser.add_argument("description", nargs="?", default="", help="文案/描述")
    parser.add_argument(
        "tags",
        nargs="?",
        default="",
        help="标签，逗号分隔，最多 4 个。如: 生活记录,日常,vlog",
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

    tags_list = [str(t).replace("#", "").strip() for t in args.tags.split(",") if t.strip()][:4]
    desc = args.description or ""
    # OpenClaw 等只传 3 个参数，标签写在文案里 (#xxx)，需提取
    if not tags_list and "#" in desc:
        desc, tags_list = extract_tags_from_description(desc, max_tags=4)
    ok = upload(
        video_path=args.video_path,
        title=args.title,
        description=desc,
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
