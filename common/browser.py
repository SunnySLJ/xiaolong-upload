# -*- coding: utf-8 -*-
"""
共享浏览器模块 - nodriver + CDP 连接 Chrome

根据 AUTH_MODE 支持三种模式：
  - cookie : 每次启动新 Chrome，通过 cookie 文件保存/加载登录态
  - connect: 连接已打开的 Chrome（需先启动带 remote-debugging-port 的 Chrome）
  - profile: 使用固定用户目录，登录态持久化（推荐）
"""
import asyncio
import os
import platform
from pathlib import Path
from typing import Callable, Optional

import nodriver as uc
from nodriver import Config

def _default_chrome_path(chrome_path: Optional[str] = None) -> str:
    if chrome_path:
        return chrome_path
    from common.conf import LOCAL_CHROME_PATH
    return LOCAL_CHROME_PATH


def get_profile_dir(
    account_name: str,
    profile_prefix: str,
    cookies_dir: Path,
    chrome_user_data_dir: str,
) -> Path:
    """AUTH_MODE=profile 时使用的 Chrome 用户目录"""
    base = (chrome_user_data_dir or "").strip() or str(cookies_dir / "chrome_profile")
    name = f"{profile_prefix}_{account_name}" if profile_prefix else account_name
    return Path(base) / name


async def get_browser(
    *,
    account_name: str = "default",
    profile_prefix: str = "",
    cookies_dir: Path,
    chrome_user_data_dir: str,
    auth_mode: str,
    cdp_endpoint: str,
    cdp_debug_port: int,
    chrome_path: Optional[str] = None,
    headless: Optional[bool] = None,
    try_reuse_chrome: bool = False,
    detach_env_var: Optional[str] = None,
    on_reuse: Optional[Callable[[], None]] = None,
    return_reused: bool = False,
):
    """
    获取 nodriver Browser 实例

    :param profile_prefix: profile 子目录前缀，如 "ks"、"sph"；空则不加前缀
    :param try_reuse_chrome: 是否先尝试连接已存在的 Chrome（固定端口）
    :param detach_env_var: 环境变量名，若为 "1" 则 Chrome 以独立会话启动
    :param on_reuse: 复用 Chrome 成功时的回调（如打日志）
    :param return_reused: 若 True，返回 (browser, was_reused)，was_reused 时调用方不应 stop() 以免关闭用户已打开的浏览器
    """
    from common.conf import LOCAL_CHROME_HEADLESS

    headless = headless if headless is not None else LOCAL_CHROME_HEADLESS
    chrome_path = _default_chrome_path(chrome_path)
    config = Config(
        headless=headless,
        browser_executable_path=chrome_path,
        sandbox=False,
    )

    # connect: 连接已有 Chrome；cookie 模式在 try_reuse 时也可连接（用于 connect 脚本 + cookie 文件）
    if auth_mode == "connect" or (auth_mode == "cookie" and try_reuse_chrome and cdp_debug_port):
        try:
            port = int(cdp_endpoint.rstrip("/").rsplit(":", 1)[-1])
        except (ValueError, IndexError):
            port = cdp_debug_port
        # connect 模式的关键：只 attach 到已有浏览器，避免再拉起临时 Chrome
        # 否则可能出现连接被抢占/端口断连（上传中 ConnectionRefused）。
        browser = await uc.start(host="127.0.0.1", port=port)
        if return_reused:
            return browser, True
        return browser

    if auth_mode == "profile":
        profile_path = get_profile_dir(
            account_name, profile_prefix, cookies_dir, chrome_user_data_dir
        )
        profile_path.mkdir(parents=True, exist_ok=True)
        config.user_data_dir = str(profile_path)

        if try_reuse_chrome:
            try:
                # 先尝试接管已存在的同端口调试浏览器，减少重复登录。
                connect_config = Config(
                    headless=headless,
                    browser_executable_path=chrome_path,
                    sandbox=False,
                    host="127.0.0.1",
                    port=cdp_debug_port,
                )
                browser = await uc.start(connect_config)
                if on_reuse:
                    on_reuse()
                if return_reused:
                    return browser, True
                return browser
            except Exception:
                pass
            try:
                import nodriver.core.util as _uc_util
                _orig = _uc_util.free_port
                # 复用失败时固定端口新开，保持平台行为可预测。
                _uc_util.free_port = lambda: cdp_debug_port
                try:
                    browser = await uc.start(config)
                    if return_reused:
                        return browser, False
                    return browser
                finally:
                    _uc_util.free_port = _orig
            except Exception:
                pass

    if detach_env_var and auth_mode != "connect":
        _maybe_patch_detach(detach_env_var)

    browser = await uc.start(config)
    if return_reused:
        return browser, False
    return browser


_patch_applied = False


def _maybe_patch_detach(env_var: str) -> None:
    """若环境变量为 1，patch create_subprocess_exec 使 Chrome 独立会话"""
    global _patch_applied
    if _patch_applied:
        return
    if os.environ.get(env_var, "").strip() not in ("1", "true", "yes"):
        return
    if platform.system() not in ("Darwin", "Linux"):
        return

    _orig = asyncio.create_subprocess_exec

    async def _patched(*args, **kwargs):
        kwargs.setdefault("start_new_session", True)
        return await _orig(*args, **kwargs)

    asyncio.create_subprocess_exec = _patched
    _patch_applied = True
