#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Upload one video via the unified upload entrypoint.

Current queue and login check path are limited to Shipinhao.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from common.console import ensure_console_ready, safe_print
from upload import upload
try:
    from scripts.platform_login import check_platform_login, login_instruction
except ImportError:
    from platform_login import check_platform_login, login_instruction

ensure_console_ready()

PLATFORM_ORDER = (
    # 登录检查当前只支持视频号，因此默认队列也只保留视频号。
    # "douyin",
    # "kuaishou",
    "shipinhao",
    # "xiaohongshu",
)

PLATFORM_CONTENT = {
    "douyin": {
        "title": "今日份生活小记录",
        "description": "把今天的片段收进这支小视频里，平凡日子也值得被认真记录。欢迎留言聊聊你的感受。",
        "tags": ["生活记录", "日常分享", "美好时光", "vlog"],
    },
    "xiaohongshu": {
        "title": "今日份生活小记录",
        "description": "把今天的小片段认真收好，平凡生活也有闪光时刻。欢迎来评论区一起聊天。",
        "tags": ["生活记录", "日常分享", "美好时光", "vlog", "小确幸"],
    },
    "kuaishou": {
        "title": "记录生活小确幸",
        "description": "把今天的片段剪成一支短视频，留住日常里的小美好。喜欢的话点个赞。",
        "tags": ["生活记录", "日常分享", "美好时光", "vlog"],
    },
    "shipinhao": {
        "title": "今日份生活小记录",
        "description": "把今天的片段整理成一支视频，留住那些值得回看的日常瞬间。感谢观看，欢迎互动。",
        "tags": ["生活记录", "日常分享", "美好时光", "vlog", "小确幸", "随手拍"],
    },
}

def _default_video_path() -> Path:
    return Path.home() / "Desktop" / "2.mp4"


def _parse_platforms(argv: list[str]) -> tuple[list[str], list[str]]:
    selected = list(PLATFORM_ORDER)
    extra_args: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--only":
            if i + 1 >= len(argv):
                raise SystemExit("错误: --only 后面需要平台列表，例如 --only douyin,kuaishou")
            selected = [item.strip() for item in argv[i + 1].split(",") if item.strip()]
            i += 2
            continue
        extra_args.append(arg)
        i += 1
    invalid = [item for item in selected if item not in PLATFORM_CONTENT]
    if invalid:
        raise SystemExit(f"错误: 不支持的平台: {', '.join(invalid)}")
    return selected, extra_args


def main() -> int:
    platforms, extra_args = _parse_platforms(sys.argv[1:])
    video_path = Path(extra_args[0]) if extra_args else _default_video_path()
    if not video_path.is_file():
        safe_print(f"错误: 视频不存在: {video_path}")
        return 1

    safe_print(f"视频: {video_path}")
    safe_print(f"即将按顺序上传到: {' -> '.join(platforms)}")
    safe_print()

    results: list[tuple[str, str]] = []
    for platform in platforms:
        content = PLATFORM_CONTENT[platform]
        safe_print(f"========== [{platform}] ==========")
        safe_print(f"标题: {content['title']}")
        safe_print(f"文案: {content['description']}")
        safe_print(f"标签: {', '.join(content['tags'])}")

        login_ok, login_msg = check_platform_login(platform, _ROOT, passive=True)
        safe_print(f"登录检查: {login_msg}")
        if not login_ok:
            safe_print(login_instruction(platform, _ROOT))
            safe_print("结果: 跳过（需先登录）")
            results.append((platform, "skipped_login"))
            safe_print()
            continue

        ok = upload(
            platform=platform,
            video_path=str(video_path.resolve()),
            title=content["title"],
            description=content["description"],
            tags=content["tags"],
        )
        results.append((platform, "success" if ok else "failed"))
        safe_print(f"结果: {'成功' if ok else '失败'}")
        safe_print()

    failed = [platform for platform, status in results if status == "failed"]
    safe_print("========== [summary] ==========")
    for platform, status in results:
        if status == "success":
            safe_print(f"{platform}: 成功")
        elif status == "skipped_login":
            safe_print(f"{platform}: 跳过（需先登录）")
        else:
            safe_print(f"{platform}: 失败")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
