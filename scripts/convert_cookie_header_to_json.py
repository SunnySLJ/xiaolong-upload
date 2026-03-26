#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把浏览器里复制的「一整段 Cookie 请求头」（name=value; name2=value2; ...）
转成 xiaolong-upload / import_cookie_and_upload 使用的 JSON：{"cookies":[...]}。

用法:
  python scripts/convert_cookie_header_to_json.py 输入.txt -o 输出.json
  type 某文件.txt | python scripts/convert_cookie_header_to_json.py -o 输出.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

DOMAIN_BY_PLATFORM = {
    "xiaohongshu": ".xiaohongshu.com",
    "douyin": ".douyin.com",
    "kuaishou": ".kuaishou.com",
    "shipinhao": ".weixin.qq.com",
}


def parse_semicolon_pairs(s: str) -> dict[str, str]:
    out: dict[str, str] = {}
    flat = " ".join(line.strip() for line in s.splitlines() if line.strip())
    for segment in flat.split(";"):
        segment = segment.strip()
        if not segment or "=" not in segment:
            continue
        name, _, value = segment.partition("=")
        name, value = name.strip(), value.strip()
        if name:
            out[name] = value
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Cookie 请求头字符串 -> Playwright 风格 JSON")
    parser.add_argument("input", nargs="?", help="含分号 cookie 的文本文件；省略则从 stdin 读取")
    parser.add_argument("-o", "--output", help="输出 .json 路径；省略则打印到 stdout")
    parser.add_argument(
        "--platform",
        default="xiaohongshu",
        choices=list(DOMAIN_BY_PLATFORM.keys()),
        help="用于写入每条 cookie 的 domain（须与上传平台一致）",
    )
    args = parser.parse_args()

    if args.input:
        raw = Path(args.input).read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()

    pairs = parse_semicolon_pairs(raw)
    if not pairs:
        print("未解析到任何 name=value，请确认内容形如: a=1; b=2", file=sys.stderr)
        return 1

    domain = DOMAIN_BY_PLATFORM[args.platform]
    exp = int(time.time()) + 365 * 86400
    cookies = [
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
        for name, value in sorted(pairs.items())
    ]
    payload = {"cookies": cookies}
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(f"已写入 {args.output}，共 {len(cookies)} 条 cookie。", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
