#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export cookies via raw CDP websocket: Network.getAllCookies
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlparse

import websockets


def _get_ws_debugger_url(port: int) -> str:
    with urlopen(f"http://127.0.0.1:{port}/json/version", timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["webSocketDebuggerUrl"]


def _get_page_ws_url(port: int, base_url: str) -> str | None:
    host = urlparse(base_url).netloc
    with urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as resp:
        pages = json.loads(resp.read().decode("utf-8"))
    for page in pages:
        if page.get("type") != "page":
            continue
        url = page.get("url", "")
        if host and host in url:
            return page.get("webSocketDebuggerUrl")
    for page in pages:
        if page.get("type") == "page" and page.get("webSocketDebuggerUrl"):
            return page.get("webSocketDebuggerUrl")
    return None


async def _fetch_cookies(ws_url: str, timeout: float, base_url: str | None = None) -> list[dict]:
    async with websockets.connect(ws_url, open_timeout=timeout, close_timeout=timeout) as ws:
        req_id = 1
        if base_url:
            await ws.send(json.dumps({"id": req_id, "method": "Network.getCookies", "params": {"urls": [base_url]}}))
        else:
            await ws.send(json.dumps({"id": req_id, "method": "Network.getAllCookies"}))
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msg = json.loads(raw)
            if msg.get("id") == req_id:
                return msg.get("result", {}).get("cookies", [])


def main() -> int:
    parser = argparse.ArgumentParser(description="Export cookies using raw CDP")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--url", default="", help="Platform page url for page-level cookie export")
    args = parser.parse_args()

    out = Path(args.output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        ws_url = None
        if args.url:
            ws_url = _get_page_ws_url(args.port, args.url)
        if ws_url:
            cookies = asyncio.run(_fetch_cookies(ws_url, args.timeout, base_url=args.url))
        else:
            ws_url = _get_ws_debugger_url(args.port)
            cookies = asyncio.run(_fetch_cookies(ws_url, args.timeout))
        out.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"COOKIE_EXPORTED: {out}")
        print(f"COOKIE_COUNT: {len(cookies)}")
        return 0
    except Exception as e:
        print(f"COOKIE_EXPORT_FAILED: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
