#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Attach to an existing Chrome (CDP), import cookies, refresh target URL, and verify login state.

Cookie file may be:
- JSON array of CDP/Playwright-style cookie objects, or {\"cookies\": [...]}
- Semicolon-separated \"name=value; ...\" (e.g. browser copy); domain is chosen from --platform
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import websockets

DOUYIN_SESSION_COOKIE_NAMES = frozenset(
    {
        "sessionid",
        "sessionid_ss",
        "sid_tt",
        "sid_guard",
        "uid_tt",
        "odin_tt",
        "ttwid",
        "passport_auth_status",
        "sid_ucp_v1",
    }
)


def _douyin_storage_has_login_cookies(cookies: list) -> bool:
    if not isinstance(cookies, list):
        return False
    names = {c.get("name") for c in cookies if isinstance(c, dict)}
    return bool(names & DOUYIN_SESSION_COOKIE_NAMES)


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


async def _ws_cmd(ws, *, method: str, params: dict | None = None, session_id: str | None = None, timeout: float = 12.0):
    """Send a CDP command and wait for its response."""
    _ws_cmd.req_id += 1
    req_id = _ws_cmd.req_id
    msg: dict = {"id": req_id, "method": method}
    if params:
        msg["params"] = params
    if session_id:
        msg["sessionId"] = session_id
    await ws.send(json.dumps(msg))
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        data = json.loads(raw)
        if data.get("id") == req_id:
            if "error" in data:
                raise RuntimeError(f"{method} failed: {data['error']}")
            return data.get("result")


_ws_cmd.req_id = 0


async def _cdp_set_raw_cookies(port: int, cookies: list[dict], timeout: float = 12.0) -> None:
    ws_url = _get_ws_debugger_url(port)
    async with websockets.connect(ws_url, open_timeout=timeout, close_timeout=timeout) as ws:
        # Network domain commands must be sent in a page session (not the browser target).
        create = await _ws_cmd(ws, method="Target.createTarget", params={"url": "about:blank"}, timeout=timeout)
        target_id = (create or {}).get("targetId")
        if not target_id:
            raise RuntimeError("Target.createTarget returned no targetId")

        attach = await _ws_cmd(
            ws,
            method="Target.attachToTarget",
            params={"targetId": target_id, "flatten": True},
            timeout=timeout,
        )
        session_id = (attach or {}).get("sessionId")
        if not session_id:
            raise RuntimeError("Target.attachToTarget returned no sessionId")

        await _ws_cmd(ws, method="Network.enable", session_id=session_id, timeout=timeout)
        try:
            await _ws_cmd(ws, method="Network.clearBrowserCookies", session_id=session_id, timeout=timeout)
        except Exception:
            # Some Chrome versions may not expose this; we'll still try setCookies.
            pass

        result = await _ws_cmd(
            ws,
            method="Network.setCookies",
            params={"cookies": cookies},
            session_id=session_id,
            timeout=timeout,
        )
        if (result or {}).get("success") is False:
            raise RuntimeError("Network.setCookies returned success=false")

        try:
            await _ws_cmd(ws, method="Target.closeTarget", params={"targetId": target_id}, timeout=timeout)
        except Exception:
            pass


def _semicolon_cookie_domain(platform: str) -> str:
    return {
        "xiaohongshu": ".xiaohongshu.com",
        "douyin": ".douyin.com",
        "kuaishou": ".kuaishou.com",
        "shipinhao": ".weixin.qq.com",
    }.get(platform, ".xiaohongshu.com")


def _parse_semicolon_cookie_pairs(s: str) -> dict[str, str]:
    """Parse 'a=1; b=2' (browser / DevTools copy). Duplicate names: last wins."""
    out: dict[str, str] = {}
    flat = " ".join(line.strip() for line in s.splitlines() if line.strip())
    for segment in flat.split(";"):
        segment = segment.strip()
        if not segment or "=" not in segment:
            continue
        name, _, value = segment.partition("=")
        name = name.strip()
        value = value.strip()
        if name:
            out[name] = value
    return out


def _semicolon_header_to_cdp_cookies(raw_text: str, platform: str) -> list[dict]:
    merged = _parse_semicolon_cookie_pairs(raw_text)
    if not merged:
        raise ValueError("no name=value pairs in semicolon cookie string")
    domain = _semicolon_cookie_domain(platform)
    exp = int(time.time()) + 365 * 86400
    cookies: list[dict] = []
    for name, value in merged.items():
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
                "expires": exp,
                "httpOnly": False,
                "secure": False,
                "sameSite": "Lax",
            }
        )
    return cookies


def _load_cookies_from_file_text(raw_text: str, platform: str) -> list[dict]:
    raw_text = raw_text.strip()
    if not raw_text:
        raise ValueError("empty cookie file")
    if raw_text.startswith("[") or raw_text.startswith("{"):
        payload = json.loads(raw_text)
        raw_cookies = payload.get("cookies") if isinstance(payload, dict) else payload
        if not isinstance(raw_cookies, list):
            raise ValueError("cookie file JSON must be a list, or an object with 'cookies' list")
        return raw_cookies
    return _semicolon_header_to_cdp_cookies(raw_text, platform)


def _has_login_gate_from_text(url: str, page_text: str, platform: str) -> bool:
    u = (url or "").lower()
    if any(x in u for x in ("/login", "passport", "signin")):
        return True
    markers = LOGIN_TEXT_MAP.get(platform, ["登录", "扫码登录"])
    t = page_text or ""
    return any(m in t for m in markers)


async def _cdp_open_and_get_text(port: int, url: str, wait_seconds: float, timeout: float = 12.0) -> tuple[str, str]:
    """
    Create a new tab, navigate, wait, then return (final_url, body_text) using pure CDP.
    Avoids nodriver runtime dependency (more reliable for cookie validation).
    """
    ws_url = _get_ws_debugger_url(port)
    async with websockets.connect(ws_url, open_timeout=timeout, close_timeout=timeout) as ws:
        create = await _ws_cmd(ws, method="Target.createTarget", params={"url": "about:blank"}, timeout=timeout)
        target_id = (create or {}).get("targetId")
        if not target_id:
            raise RuntimeError("Target.createTarget returned no targetId")

        attach = await _ws_cmd(
            ws,
            method="Target.attachToTarget",
            params={"targetId": target_id, "flatten": True},
            timeout=timeout,
        )
        session_id = (attach or {}).get("sessionId")
        if not session_id:
            raise RuntimeError("Target.attachToTarget returned no sessionId")

        await _ws_cmd(ws, method="Page.enable", session_id=session_id, timeout=timeout)
        await _ws_cmd(ws, method="Runtime.enable", session_id=session_id, timeout=timeout)

        await _ws_cmd(ws, method="Page.navigate", params={"url": url}, session_id=session_id, timeout=timeout)
        await asyncio.sleep(wait_seconds)

        # read location.href + visible text markers
        href_res = await _ws_cmd(
            ws,
            method="Runtime.evaluate",
            params={"expression": "location.href", "returnByValue": True},
            session_id=session_id,
            timeout=timeout,
        )
        final_url = ((href_res or {}).get("result") or {}).get("value") or url

        text_res = await _ws_cmd(
            ws,
            method="Runtime.evaluate",
            params={
                "expression": "document.body ? document.body.innerText : document.documentElement.innerText",
                "returnByValue": True,
            },
            session_id=session_id,
            timeout=timeout,
        )
        page_text = ((text_res or {}).get("result") or {}).get("value") or ""

        # best-effort cleanup tab
        try:
            await _ws_cmd(ws, method="Target.closeTarget", params={"targetId": target_id}, timeout=timeout)
        except Exception:
            pass

        return final_url, page_text


async def _cdp_inject_origins_localstorage(port: int, origins: list, timeout: float = 12.0) -> None:
    """Playwright storageState 里的 origins[].localStorage 一并写入（抖音等站依赖）。"""
    for block in origins:
        if not isinstance(block, dict):
            continue
        origin = (block.get("origin") or "").strip()
        ls_items = block.get("localStorage") or []
        if not origin or not ls_items:
            continue
        ws_url = _get_ws_debugger_url(port)
        async with websockets.connect(ws_url, open_timeout=timeout, close_timeout=timeout) as ws:
            create = await _ws_cmd(ws, method="Target.createTarget", params={"url": "about:blank"}, timeout=timeout)
            target_id = (create or {}).get("targetId")
            if not target_id:
                continue

            attach = await _ws_cmd(
                ws,
                method="Target.attachToTarget",
                params={"targetId": target_id, "flatten": True},
                timeout=timeout,
            )
            session_id = (attach or {}).get("sessionId")
            if not session_id:
                try:
                    await _ws_cmd(ws, method="Target.closeTarget", params={"targetId": target_id}, timeout=timeout)
                except Exception:
                    pass
                continue

            await _ws_cmd(ws, method="Page.enable", session_id=session_id, timeout=timeout)
            await _ws_cmd(ws, method="Runtime.enable", session_id=session_id, timeout=timeout)
            await _ws_cmd(ws, method="Page.navigate", params={"url": origin}, session_id=session_id, timeout=timeout)
            await asyncio.sleep(1.8)

            n_ok = 0
            for item in ls_items:
                if not isinstance(item, dict):
                    continue
                k, v = item.get("name"), item.get("value")
                if k is None or v is None:
                    continue
                expr = (
                    "(function(){try{localStorage.setItem("
                    + json.dumps(str(k))
                    + ","
                    + json.dumps(str(v))
                    + ");return 1;}catch(e){return 0}})()"
                )
                try:
                    await _ws_cmd(
                        ws,
                        method="Runtime.evaluate",
                        params={"expression": expr, "returnByValue": True},
                        session_id=session_id,
                        timeout=min(timeout, 60.0),
                    )
                    n_ok += 1
                except Exception:
                    pass

            print(f"LOCALSTORAGE_INJECT: {origin} ({n_ok}/{len(ls_items)} keys)")
            try:
                await _ws_cmd(ws, method="Target.closeTarget", params={"targetId": target_id}, timeout=timeout)
            except Exception:
                pass


async def _run(args) -> int:
    raw_text = Path(args.cookie_file).read_text(encoding="utf-8")
    raw_cookies = _load_cookies_from_file_text(raw_text, args.platform)

    if args.platform == "douyin" and not _douyin_storage_has_login_cookies(raw_cookies):
        print(
            "COOKIE_NOT_VALID: dy.json 缺少抖音账号登录 Cookie（需要至少包含 sessionid、sid_tt、uid_tt、ttwid、odin_tt、passport_auth_status 等之一）。"
            "仅 localStorage 或 csrf 类 Cookie 无法登录。"
            "请：1) 用端口 9224 的 Chrome 打开 https://creator.douyin.com 并扫码登录；"
            "2) 登录成功后运行 scripts/export_douyin_cookie.ps1 覆盖导出 dy.json；"
            "3) 再重新执行导入/上传。"
        )
        return 2

    await _cdp_set_raw_cookies(args.port, raw_cookies, timeout=12.0)

    origins = None
    s = raw_text.strip()
    if s.startswith("{"):
        try:
            payload = json.loads(s)
            origins = payload.get("origins") if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            origins = None
    if isinstance(origins, list) and origins:
        await _cdp_inject_origins_localstorage(args.port, origins, timeout=12.0)

    final_url, page_text = await _cdp_open_and_get_text(args.port, args.url, args.wait_seconds, timeout=12.0)
    if _has_login_gate_from_text(final_url, page_text, args.platform):
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
