# -*- coding: utf-8 -*-
"""
纯 CDP 模式：使用 nodriver 连接 Chrome
委托 common.browser，支持复用已打开的 Chrome、DOUYIN_DETACH_BROWSER
"""
import sys
from pathlib import Path
import asyncio
import urllib.parse
import urllib.request

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
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
from common.loggers import douyin_logger

DOUYIN_UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"


def _on_reuse():
    douyin_logger.info("[+] 复用已打开的 Chrome")


def _find_existing_upload_tab(browser, url_hint: str = DOUYIN_UPLOAD_URL):
    hint = (url_hint or "").lower()
    try:
        tabs = getattr(browser, "tabs", None) or []
        for tab in tabs:
            try:
                url = (getattr(tab, "url", None) or getattr(getattr(tab, "target", None), "url", None) or "").lower()
                if "creator.douyin.com" in url and "content/upload" in url:
                    return tab
                if hint and url == hint:
                    return tab
            except Exception:
                continue
    except Exception:
        pass
    return None


async def get_browser(*, headless=None, account_name: str = "default", return_reused: bool = True, try_reuse: bool = True):
    """获取浏览器，return_reused=True 时返回 (browser, was_reused)，复用时不调用 stop()"""
    return await _get_browser(
        account_name=account_name,
        profile_prefix="dy",  # 避免与默认 profile 冲突
        cookies_dir=COOKIES_DIR,
        chrome_user_data_dir=CHROME_USER_DATA_DIR,
        auth_mode=AUTH_MODE,
        cdp_endpoint=CDP_ENDPOINT,
        cdp_debug_port=CDP_DEBUG_PORT,
        chrome_path=LOCAL_CHROME_PATH,
        headless=headless,
        try_reuse_chrome=try_reuse,
        detach_env_var="DOUYIN_DETACH_BROWSER",
        on_reuse=_on_reuse,
        return_reused=return_reused,
    )


async def try_connect_existing_chrome(port: int = None) -> "tuple|None":
    """尝试连接已打开的 Chrome（--remote-debugging-port）。若已登录则返回 (browser, tab)。"""
    import nodriver as uc
    from nodriver import Config

    port = port or CDP_DEBUG_PORT

    def _open_target_tab(url: str) -> bool:
        encoded = urllib.parse.quote(url, safe=":/?&=%")
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/json/new?{encoded}",
                method="PUT",
                headers={"User-Agent": "douyin-connect"},
            )
            with urllib.request.urlopen(req, timeout=3):
                return True
        except Exception:
            return False

    async def _browser_get_with_retry(browser, url: str, retries: int = 2):
        last_error = None
        existing = _find_existing_upload_tab(browser, url)
        if existing is not None:
            return existing
        for _ in range(retries + 1):
            try:
                return await browser.get(url)
            except (StopIteration, RuntimeError) as e:
                last_error = e
                if "StopIteration" not in str(e) and "coroutine raised StopIteration" not in str(e):
                    raise
                _open_target_tab(url)
                await asyncio.sleep(1.5)
        raise RuntimeError(f"browser.get failed after retry: {last_error}")

    try:
        config = Config(
            port=port,
            host="127.0.0.1",
            headless=False,
            browser_executable_path=LOCAL_CHROME_PATH or None,
            sandbox=False,
        )
        browser = await uc.start(config)
        tab = await _browser_get_with_retry(browser, DOUYIN_UPLOAD_URL)
        await tab.sleep(2)
        if "creator-micro/content/upload" not in (tab.url or ""):
            # 勿 stop：会关掉用户本机已开的调试 Chrome，仅表示本次不接管
            return None
        try:
            if await tab.find("手机号登录", timeout=1) or await tab.find("扫码登录", timeout=1):
                return None
        except Exception:
            pass
        return (browser, tab)
    except Exception:
        return None
