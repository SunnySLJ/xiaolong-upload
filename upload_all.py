#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
龙虾上传 - 四平台批量上传入口

用法:
  python upload_all.py <视频路径> "标题" "文案" "标签"

特点:
  - 逐个平台串行调用统一上传入口
  - 登录失效则跳过该平台，继续下一个
  - 全部完成后汇总报告并统一关闭浏览器
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from common.python_runtime import ensure_preferred_python_3_11
from common.console import ensure_console_ready, safe_print

ensure_preferred_python_3_11()
ensure_console_ready()

if sys.version_info < (3, 10):
    safe_print("错误：需要 Python 3.10+")
    sys.exit(1)

# 导入上传函数
try:
    from upload import upload
except ImportError:
    safe_print("错误：无法导入 upload 模块")
    sys.exit(1)

# 本地批量入口当前只保留视频号；其他平台实现先保留，不在入口暴露。
PLATFORM_ORDER = [
    # "douyin",
    # "kuaishou",
    "shipinhao",
    # "xiaohongshu",
]

PLATFORM_LABELS = {
    "douyin": "抖音",
    "xiaohongshu": "小红书",
    "kuaishou": "快手",
    "shipinhao": "视频号",
}


def upload_to_platform(
    platform: str,
    video_path: str,
    title: str,
    description: str,
    tags: list,
    close_browser: bool = True,  # 是否在此平台上传后关闭浏览器
) -> Tuple[bool, str]:
    """
    上传到单个平台
    流程：直接调用 upload 函数处理当前平台的登录和上传
    返回：(成功与否，消息)
    """
    label = PLATFORM_LABELS.get(platform, platform)
    safe_print(f"\n{'='*50}")
    safe_print(f"📤 开始处理：{label}")
    safe_print(f"{'='*50}")
    
    # 直接调用 upload 函数，让它处理登录检查和上传
    # 不再单独调用 check_platform_login，避免两次检查导致浏览器状态不一致
    safe_print(f"⏳ 检查登录并上传视频中...")
    
    success = upload(
        platform=platform,
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        handle_login=True,  # 让 upload 函数处理登录
        close_browser=close_browser,  # 控制是否关闭浏览器
    )
    
    if success:
        safe_print(f"✅ {label} 发布成功")
        return True, "发布成功"
    else:
        safe_print(f"❌ {label} 发布失败")
        return False, "发布失败"


def upload_all_platforms(
    video_path: str,
    title: str,
    description: str,
    tags: list,
    platforms: List[str] | None = None,
) -> dict:
    """
    批量上传到多个平台
    返回：{platform: (success, message)}
    """
    platforms = platforms or PLATFORM_ORDER
    
    results = {}
    
    safe_print(f"\n{'='*60}")
    safe_print(f"🦐 龙虾上传 - 四平台批量上传")
    safe_print(f"{'='*60}")
    safe_print(f"📹 视频：{video_path}")
    safe_print(f"📝 标题：{title}")
    safe_print(f"💬 文案：{description[:50]}...")
    safe_print(f"🏷️ 标签：{', '.join(tags)}")
    safe_print(f"📋 平台顺序：{' → '.join([PLATFORM_LABELS.get(p, p) for p in platforms])}")
    safe_print(f"{'='*60}")
    
    # 上传所有平台（close_browser=False，等全部完成后再统一关闭）
    for platform in platforms:
        success, message = upload_to_platform(
            platform=platform,
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            close_browser=False,  # 多平台模式下不单独关闭浏览器
        )
        results[platform] = (success, message)
    
    # 所有平台完成后，统一关闭浏览器
    safe_print(f"\n{'='*60}")
    safe_print(f"🔒 统一关闭浏览器...")
    from skills.auth.scripts.platform_login import close_connect_browser
    for platform in platforms:
        success, _ = results[platform]
        if success:
            label = PLATFORM_LABELS.get(platform, platform)
            try:
                close_connect_browser(platform)
                safe_print(f"✓ {label} 浏览器已关闭")
            except Exception as e:
                safe_print(f"⚠ {label} 关闭浏览器失败：{e}")
    safe_print(f"{'='*60}")
    
    # 汇总报告
    safe_print(f"\n{'='*60}")
    safe_print(f"📊 发布结果汇总")
    safe_print(f"{'='*60}")
    
    success_count = sum(1 for _, (success, _) in results.items() if success)
    total_count = len(results)
    
    for platform, (success, message) in results.items():
        label = PLATFORM_LABELS.get(platform, platform)
        icon = "✅" if success else "❌"
        safe_print(f"{icon} {label}: {message}")
    
    safe_print(f"\n总计：{success_count}/{total_count} 平台发布成功")
    safe_print(f"{'='*60}\n")
    
    return results


def _main():
    import argparse

    parser = argparse.ArgumentParser(
        description="龙虾上传 - 四平台批量上传",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python upload_all.py /path/video.mp4 "标题" "文案" "标签 1,标签 2"
  python upload_all.py video.mp4 "标题"
        """,
    )
    parser.add_argument("video_path", help="视频文件路径")
    parser.add_argument("title", nargs="?", default="", help="标题")
    parser.add_argument("description", nargs="?", default="", help="文案")
    parser.add_argument("tags", nargs="?", default="", help="标签，逗号分隔")
    parser.add_argument(
        "--platforms",
        "-p",
        nargs="+",
        choices=PLATFORM_ORDER,
        default=None,
        help="要上传的平台列表（当前入口仅保留 shipinhao）",
    )
    parser.add_argument(
        "--platform",
        choices=PLATFORM_ORDER,
        help="只上传到单个平台（当前入口仅保留 shipinhao）",
    )

    args = parser.parse_args()

    # 解析标签
    tags_list = [t.strip() for t in args.tags.split(",") if t.strip()]
    
    # 确定平台列表
    if args.platform:
        # 单个平台
        platforms = [args.platform]
        safe_print(f"🎯 只上传到：{PLATFORM_LABELS.get(args.platform, args.platform)}")
    elif args.platforms:
        # 多个平台
        platforms = args.platforms
    else:
        # 默认全部平台
        platforms = PLATFORM_ORDER

    results = upload_all_platforms(
        video_path=args.video_path,
        title=args.title,
        description=args.description,
        tags=tags_list,
        platforms=platforms,
    )

    # 根据结果设置退出码
    success_count = sum(1 for _, (success, _) in results.items() if success)
    sys.exit(0 if success_count > 0 else 1)


if __name__ == "__main__":
    _main()
