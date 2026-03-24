#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Attach to an existing Chrome (CDP), import cookie JSON, refresh target URL, and verify login state.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from urllib.request import urlopen

import nodriver as uc
import websockets


LOGIN_TEXT_MAP = {
    "douyin": ["扫码登录", "手机号登录", "验证码登录", "登录抖音创作者中心"],
    "xiaohongshu": ["手机号登录", "验证码登录", "立即登录", "请登录后发布"],
    "kuaishou": ["手机号登录", "验证码登录", "请先登录", "去登录"],
    "shipinhao": ["微信扫码登录", "扫码登录后可继续", "请登录后继续"],
}


async def _maybe_clear_cookies(browser) -> None:
    """Best-effort clear for existing cookies before loading a new account."""
    candidates = ("clear", "clear_all", "delete_all")
    for name in candidates:
        fn = getattr(browser.cookies, name, None)
        if fn:
            await fn()
            return


def _get_ws_debugger_url(port: int) -> str:
    with urlopen(f"http://127.0.0.1:{port}/json/version", timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["webSocketDebuggerUrl"]


async def _cdp_set_raw_cookies(port: int, cookies: list[dict], timeout: float = 12.0) -> None:
    ws_url = _get_ws_debugger_url(port)
    async with websockets.connect(ws_url, open_timeout=timeout, close_timeout=timeout) as ws:
        req_id = 1
        await ws.send(json.dumps({"id": req_id, "method": "Network.clearBrowserCookies"}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            if msg.get("id") == req_id:
                break

        req_id = 2
        await ws.send(json.dumps({"id": req_id, "method": "Network.setCookies", "params": {"cookies": cookies}}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            if msg.get("id") == req_id:
                if msg.get("result", {}).get("success") is False:
                    raise RuntimeError("Network.setCookies returned success=false")
                break


async def _has_login_gate(tab, platform: str) -> bool:
    # URL 级快速判断（命中登录页特征时直接判未登录）
    u = (getattr(tab, "url", "") or "").lower()
    if any(x in u for x in ("/login", "passport", "signin")):
        return True

    markers = LOGIN_TEXT_MAP.get(platform, ["登录", "扫码登录"])
    for text in markers:
        try:
            el = await tab.find(text, timeout=1.5)
            if el is not None:
                return True
        except Exception:
            continue
    return False


async def _run(args) -> int:
    browser = await uc.start(host="127.0.0.1", port=args.port)
    tab = await browser.get(args.url)
    await tab.sleep(1.0)

    raw_text = Path(args.cookie_file).read_text(encoding="utf-8").strip()
    if raw_text.startswith("["):
        raw_cookies = json.loads(raw_text)
        await _cdp_set_raw_cookies(args.port, raw_cookies, timeout=12.0)
    else:
        await _maybe_clear_cookies(browser)
        await browser.cookies.load(str(Path(args.cookie_file).resolve()))

    tab = await browser.get(args.url)
    await tab.sleep(args.wait_seconds)

    if await _has_login_gate(tab, args.platform):
        print("COOKIE_NOT_VALID: 页面仍显示登录提示")
        return 2

    print("COOKIE_OK: 已注入并通过页面登录校验")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Import cookies into connected Chrome and verify login")
    parser.add_argument("--platform", required=True, choices=["douyin", "xiaohongshu", "kuaishou", "shipinhao"])
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--url", required=True)
    parser.add_argument("--cookie-file", required=True)
    parser.add_argument("--wait-seconds", type=float, default=2.5)
    args = parser.parse_args()

    cookie_path = Path(args.cookie_file)
    if not cookie_path.is_file():
        print(f"COOKIE_FILE_NOT_FOUND: {cookie_path}")
        return 1

    try:
        return asyncio.run(_run(args))
    except Exception as e:
        print(f"COOKIE_IMPORT_FAILED: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
