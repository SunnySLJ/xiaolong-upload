#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 cookie 字符串保存为快手上传可用的 JSON 文件

用法:
  python scripts/save_kuaishou_cookie.py "kuaishou.sessionid=xxx; did=yyy; ..."
  python scripts/save_kuaishou_cookie.py --file cookie.txt
  python scripts/save_kuaishou_cookie.py --json '[{"name":"xxx","value":"yyy",...}]'

输出: cookies/kuaishou/kuaishou_default.json
"""
import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_COOKIES_DIR = _ROOT / "cookies" / "kuaishou"
_ACCOUNT_FILE = _COOKIES_DIR / "kuaishou_default.json"


def _parse_cookie_string(s: str) -> list:
    """解析 "name=value; name2=value2" 格式为 nodriver 兼容的 JSON 列表"""
    domain = ".kuaishou.com"
    cookies = []
    for part in s.split(";"):
        part = part.strip()
        if "=" in part:
            name, _, value = part.partition("=")
            name, value = name.strip(), value.strip()
            if name:
                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": "/",
                    "secure": True,
                    "httpOnly": False,
                    "sameSite": "Lax",
                    "sameParty": False,
                })
    return cookies


def main():
    parser = argparse.ArgumentParser(description="保存快手 cookie 到文件")
    parser.add_argument("cookie", nargs="?", help="cookie 字符串")
    parser.add_argument("--file", "-f", help="从文件读取 cookie 字符串")
    parser.add_argument("--json", "-j", action="store_true", help="输入为 JSON 数组格式")
    parser.add_argument("--account", default="default", help="账号名")
    args = parser.parse_args()

    if args.account != "default":
        account_file = _COOKIES_DIR / f"kuaishou_{args.account}.json"
    else:
        account_file = _ACCOUNT_FILE

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            raw = f.read().strip()
    elif args.cookie:
        raw = args.cookie.strip()
    else:
        print("请提供 cookie 字符串，或使用 --file 指定文件")
        print('示例: python scripts/save_kuaishou_cookie.py "kuaishou.sessionid=xxx; did=yyy"')
        sys.exit(1)

    if args.json:
        try:
            cookies = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}")
            sys.exit(1)
    else:
        cookies = _parse_cookie_string(raw)

    if not cookies:
        print("未解析到有效 cookie")
        sys.exit(1)

    _COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    with open(account_file, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)

    print(f"已保存 {len(cookies)} 个 cookie 到 {account_file}")


if __name__ == "__main__":
    main()
