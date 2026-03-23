# -*- coding: utf-8 -*-
"""
纯 CDP 模式：使用 nodriver 连接 Chrome
委托 common.browser，优先复用已打开的 Chrome
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _on_reuse():
    from common.loggers import xiaohongshu_logger
    xiaohongshu_logger.info("[+] 复用已打开的 Chrome")


if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from conf import (
    LOCAL_CHROME_PATH,
    LOCAL_CHROME_HEADLESS,
    AUTH_MODE,
    CDP_ENDPOINT,
    CDP_DEBUG_PORT,
    CHROME_USER_DATA_DIR,
    COOKIES_DIR,
)
from common.browser import get_browser as _get_browser


async def get_browser(*, headless=None, account_name: str = "default", return_reused: bool = True, try_reuse: bool = True):
    """获取浏览器，return_reused=True 时返回 (browser, was_reused)，复用时不调用 stop()"""
    return await _get_browser(
        account_name=account_name,
        profile_prefix="xhs",
        cookies_dir=COOKIES_DIR,
        chrome_user_data_dir=CHROME_USER_DATA_DIR,
        auth_mode=AUTH_MODE,
        cdp_endpoint=CDP_ENDPOINT,
        cdp_debug_port=CDP_DEBUG_PORT,
        chrome_path=LOCAL_CHROME_PATH,
        headless=headless,
        try_reuse_chrome=try_reuse,
        detach_env_var=None,
        on_reuse=_on_reuse,
        return_reused=return_reused,
    )
