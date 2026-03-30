# -*- coding: utf-8 -*-
import asyncio
import platform
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

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
DOUYIN_CONNECT_PORT = 9224
DOUYIN_CONNECT_PROFILE_DIR = COOKIES_DIR.parent / "chrome_connect_dy"


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


def _open_target_tab(url: str, port: int = DOUYIN_CONNECT_PORT) -> bool:
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


def _port_listening(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def _launch_debug_chrome(port: int, url: str) -> None:
    DOUYIN_CONNECT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    kwargs = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    system = platform.system()
    if system == "Darwin":
        args = [
            "open",
            "-na",
            "Google Chrome",
            "--args",
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={DOUYIN_CONNECT_PROFILE_DIR}",
            "--start-maximized",
            url,
        ]
        kwargs["start_new_session"] = True
    else:
        chrome = LOCAL_CHROME_PATH or None
        args = [
            chrome,
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={DOUYIN_CONNECT_PROFILE_DIR}",
            "--start-maximized",
            url,
        ]
        if system == "Linux":
            kwargs["start_new_session"] = True
        elif system == "Windows":
            kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(args, **kwargs)


def ensure_connect_login_chrome(
    port: int = DOUYIN_CONNECT_PORT,
    url: str = DOUYIN_UPLOAD_URL,
    timeout: float = 15.0,
) -> bool:
    """确保抖音 connect 调试 Chrome 已启动，并固定落盘到 cookies/chrome_connect_dy。"""
    if _port_listening(port):
        DOUYIN_CONNECT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        return True

    try:
        _launch_debug_chrome(port, url)
    except Exception as e:
        douyin_logger.warning(f"[-] 启动 connect Chrome 失败: {e}")
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_listening(port):
            douyin_logger.info(f"[+] 已启动 connect Chrome，目录: {DOUYIN_CONNECT_PROFILE_DIR}")
            return True
        time.sleep(0.25)
    douyin_logger.warning("[-] connect Chrome 启动超时")
    return False


async def attach_login_chrome(port: int = DOUYIN_CONNECT_PORT):
    """连接抖音专用调试 Chrome，不要求当前已登录。"""
    import nodriver as uc
    from nodriver import Config

    config = Config(
        port=port,
        host="127.0.0.1",
        headless=False,
        browser_executable_path=LOCAL_CHROME_PATH or None,
        sandbox=False,
    )
    browser = await uc.start(config)
    tab = _find_existing_upload_tab(browser, DOUYIN_UPLOAD_URL)
    if tab is None:
        try:
            tab = await browser.get(DOUYIN_UPLOAD_URL)
        except (StopIteration, RuntimeError):
            _open_target_tab(DOUYIN_UPLOAD_URL)
            tab = await browser.get(DOUYIN_UPLOAD_URL)
    await tab.sleep(2)
    return browser, tab


async def try_connect_existing_chrome(port: int = None) -> "tuple|None":
    """尝试连接已打开的 Chrome（--remote-debugging-port）。若已登录则返回 (browser, tab)。"""
    import nodriver as uc
    from nodriver import Config

    # 抖音固定优先探测自己的 connect 端口 9224，避免误连默认 9222。
    port = port or DOUYIN_CONNECT_PORT

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
                _open_target_tab(url, port)
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
