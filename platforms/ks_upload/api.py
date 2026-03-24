# -*- coding: utf-8 -*-
"""
快手上传统一入口 - 供外部直接调用

用法：
    from api import upload_to_kuaishou
    upload_to_kuaishou(video_path="...", title="...", description="...", tags=["..."])
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
from kuaishou.main import kuaishou_setup, KuaishouVideo

ensure_console_ready()


def upload_to_kuaishou(
    video_path: str,
    title: str,
    description: str = "",
    tags: Optional[List[str]] = None,
    account_name: str = "default",
    handle_login: bool = True,
    thumbnail_path: Optional[str] = None,
    publish_date: Union[datetime, int] = 0,
) -> bool:
    """快手视频上传主函数"""
    tags = [str(t).replace("#", "").strip() for t in (tags or []) if t][:4]  # 最多 4 个
    video_path = str(Path(video_path).resolve())

    if not Path(video_path).exists():
        safe_print(f"错误: 视频文件不存在: {video_path}")
        return False

    COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    account_file = str(COOKIES_DIR / f"kuaishou_{account_name}.json")

    async def _do_upload() -> bool:
        try:
            ok, browser_tab = await kuaishou_setup(account_file, handle=handle_login, account_name=account_name)
        except Exception as e:
            import traceback
            safe_print(f"错误: 登录/校验异常: {e}")
            traceback.print_exc()
            return False
        if not ok:
            safe_print("错误: 登录校验失败，请完成扫码/验证码登录后重试")
            return False

        safe_print("登录完成，开始上传...")
        pub_date = publish_date if isinstance(publish_date, datetime) else 0
        app = KuaishouVideo(
            title=title,
            file_path=video_path,
            tags=tags,
            publish_date=pub_date,
            account_file=account_file,
            description=description,
            thumbnail_path=thumbnail_path,
            account_name=account_name,
        )
        try:
            if browser_tab:
                ok = await app.upload(existing_browser=browser_tab[0], existing_tab=browser_tab[1])
            else:
                ok = await app.upload()
        except Exception as e:
            import traceback
            safe_print(f"错误: 上传过程异常: {e}")
            traceback.print_exc()
            return False
        return ok is True

    try:
        return asyncio.run(_do_upload())
    except Exception as e:
        import traceback
        safe_print(f"错误: 上传异常: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    from upload import main
    main()
