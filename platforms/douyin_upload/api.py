# -*- coding: utf-8 -*-
"""
抖音上传统一入口 - 供外部直接调用

用法示例：
    from douyin_upload.api import upload_to_douyin

    success = upload_to_douyin(
        video_path="/path/to/video.mp4",
        title="我的视频标题",
        description="视频描述文案",
        tags=["生活记录", "日常分享"],
    )
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

# 支持从项目根目录导入（统一入口 upload.py）
_ROOT = Path(__file__).resolve().parent.parent.parent
_PLATFORM = Path(__file__).resolve().parent
for p in (_ROOT, _PLATFORM):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from common.console import ensure_console_ready, safe_print
from conf import COOKIES_DIR
from douyin.main import douyin_setup, DouYinVideo

ensure_console_ready()


def upload_to_douyin(
    video_path: str,
    title: str,
    description: str = "",
    tags: Optional[List[str]] = None,
    account_name: str = "default",
    handle_login: bool = True,
    thumbnail_path: Optional[str] = None,
    product_link: str = "",
    product_title: str = "",
    publish_date: Union[datetime, int] = 0,
) -> bool:
    """
    抖音视频上传主函数 - 统一入口，外部直接调用此函数即可完成上传。

    Args:
        video_path: 视频文件路径（必填）
        title: 视频标题，最多 30 字（必填）
        description: 视频描述/文案，可为空
        tags: 话题标签列表，如 ["生活记录", "日常分享"]
        account_name: 账号名，对应 cookies/douyin_{account_name}.json 或 profile 子目录
        handle_login: 未登录时是否打开浏览器引导扫码，False 则直接返回失败
        thumbnail_path: 自定义封面图路径，不传则使用 AI 自动选封面
        product_link: 商品链接（带货视频用）
        product_title: 商品短标题（带货视频用）
        publish_date: 定时发布时间，0 表示立即发布；datetime 对象表示定时

    Returns:
        True 表示上传成功，False 表示失败（未登录、文件不存在、超时等）

    示例：
        upload_to_douyin(
            video_path="/Users/xx/Desktop/video.mp4",
            title="记录美好生活",
            description="每一天都值得记录 ✨",
            tags=["vlog", "日常"],
        )
    """
    tags = tags or []
    video_path = str(Path(video_path).resolve())

    if not Path(video_path).exists():
        safe_print(f"错误: 视频文件不存在: {video_path}")
        return False

    COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    account_file = str(COOKIES_DIR / f"douyin_{account_name}.json")

    async def _do_upload() -> bool:
        # 1) 先做登录态校验：已登录则复用浏览器；未登录时按 handle_login 决定是否引导扫码。
        ok, browser_tab = await douyin_setup(account_file, handle=handle_login, account_name=account_name)
        if not ok:
            safe_print("错误: 登录校验失败，请完成扫码登录后重试")
            return False

        # 2) 统一整理 browser/tab，后续上传流程优先复用现有发布页标签。
        # douyin_setup 可能返回 (True, browser) 或 (True, (browser, tab))
        if isinstance(browser_tab, tuple) and len(browser_tab) == 2:
            browser, existing_tab = browser_tab
        else:
            browser, existing_tab = browser_tab, None

        pub_date = publish_date if isinstance(publish_date, datetime) else 0
        app = DouYinVideo(
            title=title,
            file_path=video_path,
            tags=tags,
            publish_date=pub_date,
            account_file=account_file,
            description=description,
            thumbnail_path=thumbnail_path,
            productLink=product_link,
            productTitle=product_title,
            account_name=account_name,
        )
        # 3) 进入上传主流程：上传文件 -> 填写标题文案话题 -> 发布。
        ok = await app.upload(browser=browser, existing_tab=existing_tab)
        return ok is True

    try:
        return asyncio.run(_do_upload())
    except Exception as e:
        safe_print(f"错误: 上传异常: {e}")
        return False


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        _tags_raw = sys.argv[4] if len(sys.argv) > 4 else ""
        _tags = [t.strip() for t in _tags_raw.split(",") if t.strip()]
        upload_to_douyin(
            video_path=sys.argv[1],
            title=sys.argv[2],
            description=sys.argv[3] if len(sys.argv) > 3 else "",
            tags=_tags,
        )
    else:
        upload_to_douyin(
            video_path="/Users/h/Desktop/3.mp4",
            title="记录美好生活",
            description="每一天都值得记录 ✨",
            tags=["vlog", "日常"],
        )
