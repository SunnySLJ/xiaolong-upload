#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create a visible CDP page target on an existing Chrome.

Some environments expose the browser WS endpoint but have 0 page targets under /json,
which can cause automation libs to fail with StopIteration. This script ensures at least
one page target exists by calling Target.createTarget and leaving it open.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from urllib.request import urlopen

import websockets


def _get_ws_debugger_url(port: int) -> str:
    with urlopen(f"http://127.0.0.1:{port}/json/version", timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["webSocketDebuggerUrl"]


async def _ws_cmd(ws, *, method: str, params: dict | None = None, timeout: float = 12.0):
    _ws_cmd.req_id += 1
    req_id = _ws_cmd.req_id
    msg: dict = {"id": req_id, "method": method}
    if params:
        msg["params"] = params
    await ws.send(json.dumps(msg))
    while True:
        data = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if data.get("id") == req_id:
            if "error" in data:
                raise RuntimeError(f"{method} failed: {data['error']}")
            return data.get("result")


_ws_cmd.req_id = 0


async def _run(port: int, url: str) -> str:
    ws_url = _get_ws_debugger_url(port)
    async with websockets.connect(ws_url, open_timeout=12, close_timeout=12) as ws:
        res = await _ws_cmd(ws, method="Target.createTarget", params={"url": url})
        tid = (res or {}).get("targetId")
        if not tid:
            raise RuntimeError("Target.createTarget returned no targetId")
        return tid


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=9223)
    p.add_argument("--url", default="about:blank")
    args = p.parse_args()
    tid = asyncio.run(_run(args.port, args.url))
    print(f"CDP_TAB_OK: {tid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

