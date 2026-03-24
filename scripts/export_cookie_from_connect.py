#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export cookies from an existing CDP Chrome session to JSON.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import nodriver as uc


async def _run(port: int, url: str, output: Path, wait_seconds: float, connect_timeout: float, skip_open: bool) -> int:
    print(f"Connecting CDP: 127.0.0.1:{port} ...")
    browser = await asyncio.wait_for(uc.start(host="127.0.0.1", port=port), timeout=connect_timeout)
    if not skip_open:
        print("CDP connected, opening upload page ...")
        tab = await asyncio.wait_for(browser.get(url), timeout=connect_timeout)
        await tab.sleep(wait_seconds)
    else:
        print("CDP connected, exporting current session cookies ...")

    output.parent.mkdir(parents=True, exist_ok=True)
    await browser.cookies.save(str(output))
    print(f"COOKIE_EXPORTED: {output}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Export cookies from connected Chrome")
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--wait-seconds", type=float, default=2.0)
    parser.add_argument("--connect-timeout", type=float, default=20.0)
    parser.add_argument("--skip-open", action="store_true", help="Do not open target URL before export")
    args = parser.parse_args()

    out = Path(args.output).resolve()
    try:
        return asyncio.run(_run(args.port, args.url, out, args.wait_seconds, args.connect_timeout, args.skip_open))
    except TimeoutError:
        print("COOKIE_EXPORT_FAILED: connect timeout")
        return 1
    except Exception as e:
        print(f"COOKIE_EXPORT_FAILED: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
