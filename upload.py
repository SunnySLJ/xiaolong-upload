#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
龙虾上传 - 四平台统一 CLI 入口

用法:
  python upload.py --platform <平台> <视频路径> [标题] [文案] [标签]

平台: shipinhao
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from common.python_runtime import ensure_preferred_python_3_11
from common.platform_auth import check_platform_login, ensure_platform_login
from common.console import ensure_console_ready, safe_print

# 导入关闭浏览器函数
try:
    from skills.auth.scripts.platform_login import close_connect_browser
except ImportError:
    close_connect_browser = None

ensure_preferred_python_3_11()
ensure_console_ready()

if sys.version_info < (3, 10):
    safe_print("错误: 需要 Python 3.10+")
    sys.exit(1)


PLATFORMS = (
    "douyin",
    "kuaishou",
    "shipinhao",
    "xiaohongshu",
)

# 本地 CLI 入口当前只保留视频号；其他平台实现先保留，不在入口暴露。
CLI_PLATFORMS = (
    # "douyin",
    # "kuaishou",
    "shipinhao",
    # "xiaohongshu",
)


def _dispatch_douyin(video_path: str, title: str, description: str, tags: list, **kw) -> bool:
    from platforms.douyin_upload.api import upload_to_douyin
    return upload_to_douyin(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        **kw,
    )


def _dispatch_kuaishou(video_path: str, title: str, description: str, tags: list, **kw) -> bool:
    from platforms.ks_upload.upload import upload
    return upload(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        **kw,
    )


def _dispatch_shipinhao(video_path: str, title: str, description: str, tags: list, **kw) -> bool:
    from platforms.shipinhao_upload.api import upload_to_shipinhao
    return upload_to_shipinhao(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        **kw,
    )


def _dispatch_xiaohongshu(video_path: str, title: str, description: str, tags: list, **kw) -> bool:
    from platforms.xhs_upload.upload import upload
    return upload(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        **kw,
    )


_DISPATCH = {
    "douyin": _dispatch_douyin,
    "kuaishou": _dispatch_kuaishou,
    "shipinhao": _dispatch_shipinhao,
    "xiaohongshu": _dispatch_xiaohongshu,
}


def upload(
    platform: str,
    video_path: str,
    title: str = "",
    description: str = "",
    tags: list | None = None,
    account_name: str = "default",
    handle_login: bool = True,
    notify_login_wechat: bool = False,
    login_only: bool = False,
    close_browser: bool = True,  # 发布成功后是否关闭浏览器（多平台批量上传时设为 False）
) -> bool:
    """
    统一上传入口
    :param platform: douyin | kuaishou | shipinhao | xiaohongshu
    :param video_path: 视频路径
    :param title: 标题（视频号可空，自动生成）
    :param description: 文案
    :param tags: 标签列表
    :param account_name: 账号名
    :param handle_login: 未登录时是否打开浏览器
    :param notify_login_wechat: 登录失效时是否把二维码发到微信
    :param login_only: 仅检查/完成登录，不继续上传
    """
    # 入口层只做路由与参数清洗，登录/上传细节由平台模块负责。
    platform = platform.lower().strip()
    if platform not in _DISPATCH:
        safe_print(f"错误: 未知平台: {platform}，可选: {', '.join(PLATFORMS)}")
        return False

    tags = tags or []
    tags = [t.strip() for t in tags if t]

    if handle_login:
        ok, msg = ensure_platform_login(
            platform,
            project_root=_PROJECT_ROOT,
            timeout=300,
            notify_wechat=notify_login_wechat,
        )
    else:
        ok, msg = check_platform_login(platform, project_root=_PROJECT_ROOT, passive=True)
    if not ok:
        safe_print(f"错误: {msg}")
        return False
    safe_print(msg)

    if login_only:
        safe_print(f"{platform} 登录检查完成，按要求不继续发布。")
        return True

    # 每个平台的 upload_to_xxx 会完成：
    # 1) 登录态校验/引导登录 2) 打开发布页 3) 上传并发布
    ok = _DISPATCH[platform](
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        account_name=account_name,
        handle_login=False,
    )
    
    # 发布成功后关闭浏览器（2026-03-31 更新）
    # close_browser=False 时由调用方统一关闭（用于多平台批量上传）
    if ok and close_connect_browser and close_browser:
        safe_print(f"✓ {platform} 发布成功，关闭浏览器...")
        try:
            close_connect_browser(platform)
            safe_print(f"✓ {platform} 浏览器已关闭")
        except Exception as e:
            safe_print(f"⚠ 关闭浏览器失败：{e}")
    
    # 发布成功后不再移动视频，由用户每周定时任务统一清理
    # published_dir 仅作为历史参考，新视频保留在原始位置
    
    return ok


def _main():
    import argparse

    parser = argparse.ArgumentParser(
        description="龙虾上传 - 四平台统一入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python upload.py --platform shipinhao video.mp4 "标题" "文案"
        """,
    )
    parser.add_argument("--platform", "-p", required=True, choices=CLI_PLATFORMS, help="目标平台")
    parser.add_argument("video_path", help="视频文件路径")
    parser.add_argument("title", nargs="?", default="", help="标题")
    parser.add_argument("description", nargs="?", default="", help="文案")
    parser.add_argument("tags", nargs="?", default="", help="标签，逗号分隔")
    parser.add_argument("--account", default="default", help="账号名")
    parser.add_argument("--no-login", action="store_true", help="未登录时不自动打开浏览器")
    parser.add_argument("--notify-login-wechat", action="store_true", help="登录失效时把二维码发到微信")
    parser.add_argument("--login-only", action="store_true", help="只完成登录检查/登录，不继续发布")
    args = parser.parse_args()

    # CLI 入参统一在这里转成标准 tags 列表，避免平台侧重复解析。
    tags_list = [t.strip() for t in args.tags.split(",") if t.strip()]

    ok = upload(
        platform=args.platform,
        video_path=args.video_path,
        title=args.title,
        description=args.description,
        tags=tags_list,
        account_name=args.account,
        handle_login=not args.no_login,
        notify_login_wechat=args.notify_login_wechat,
        login_only=args.login_only,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    _main()
