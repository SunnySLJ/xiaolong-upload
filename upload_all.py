#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
龙虾上传 - 四平台批量上传入口

用法:
  python upload_all.py <视频路径> "标题" "文案" "标签"

特点:
  - 逐个平台被动检查登录 → 上传
  - 登录失效则跳过该平台，继续下一个
  - 全部完成后汇总报告
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

# 平台顺序：抖音 > 小红书 > 快手 > 视频号
PLATFORM_ORDER = ["douyin", "xiaohongshu", "kuaishou", "shipinhao"]

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
) -> Tuple[bool, str]:
    """
    上传到单个平台
    流程：检查登录 → 如失效则自动恢复 → 上传 → 关闭浏览器
    返回：(成功与否，消息)
    """
    label = PLATFORM_LABELS.get(platform, platform)
    safe_print(f"\n{'='*50}")
    safe_print(f"📤 开始处理：{label}")
    safe_print(f"{'='*50}")
    
    # 步骤 1: 检查登录状态
    safe_print(f"🔍 检查 {label} 登录状态...")
    
    from common.platform_auth import check_platform_login
    ok, msg = check_platform_login(platform, _PROJECT_ROOT, passive=True)
    
    if not ok:
        # 步骤 1b: 登录失效，尝试自动恢复
        safe_print(f"⚠ {label} 登录失效，尝试自动恢复...")
        safe_print(f"   原因：{msg}")
        
        from skills.auth.scripts.platform_login import auto_recover_session
        recover_ok, recover_msg = auto_recover_session(platform, _PROJECT_ROOT)
        
        if not recover_ok:
            safe_print(f"❌ {label} 恢复失败，跳过该平台")
            safe_print(f"   原因：{recover_msg}")
            return False, f"跳过（恢复失败）：{recover_msg}"
        
        safe_print(f"✅ {label} 恢复成功：{recover_msg}")
    else:
        safe_print(f"✅ {label} 已登录：{msg}")
    
    # 步骤 2: 上传（handle_login=True，让 upload 函数处理浏览器）
    safe_print(f"⏳ 上传视频中...")
    
    success = upload(
        platform=platform,
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        handle_login=True,  # 让 upload 函数处理浏览器关闭
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
    
    for platform in platforms:
        success, message = upload_to_platform(
            platform=platform,
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
        )
        results[platform] = (success, message)
    
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
        help="要上传的平台列表（默认全部：douyin xiaohongshu kuaishou shipinhao）",
    )
    parser.add_argument(
        "--platform",
        choices=PLATFORM_ORDER,
        help="只上传到单个平台（--platform douyin 等同于 --platforms douyin）",
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
