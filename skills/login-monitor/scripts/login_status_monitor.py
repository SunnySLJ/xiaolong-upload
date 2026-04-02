#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定时巡检四平台登录状态，并在失效时触发重新登录流程。"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.python_runtime import ensure_preferred_python_3_11
from common.skill_runtime import resolve_project_root

ensure_preferred_python_3_11()


SKILL_ROOT = Path(__file__).resolve().parents[1]
AUTH_SCRIPT = SKILL_ROOT.parent / "auth" / "scripts" / "platform_login.py"


def _load_auth_module():
    spec = importlib.util.spec_from_file_location("skill_auth_platform_login", AUTH_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 auth 脚本: {AUTH_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUTH = _load_auth_module()


def _project_root(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    return resolve_project_root(SKILL_ROOT.parents[1])


def _normalize_platforms(values: list[str] | None) -> list[str]:
    if not values or values == ["all"]:
        return list(AUTH.PLATFORMS.keys())
    result: list[str] = []
    for item in values:
        if item == "all":
            return list(AUTH.PLATFORMS.keys())
        if item not in AUTH.PLATFORMS:
            raise ValueError(f"未知平台: {item}")
        if item not in result:
            result.append(item)
    return result


def _status_label(ok: bool) -> str:
    return "valid" if ok else "expired"


def _check_platform(platform_name: str, project_root: Path) -> dict[str, Any]:
    ok, message = AUTH.check_platform_login(platform_name, project_root)
    return {
        "platform": platform_name,
        "label": AUTH.PLATFORMS[platform_name]["label"],
        "ok": ok,
        "status": _status_label(ok),
        "message": message,
    }


def _trigger_relogin(
    platform_name: str,
    timeout: int,
    notify_wechat: bool,
) -> tuple[bool, str]:
    # wait=False: 只负责打开登录页/发送二维码，不阻塞整个巡检任务
    return AUTH.ensure_platform_login(
        platform_name,
        wait=False,
        timeout=timeout,
        notify_wechat=notify_wechat,
    )


def _run_once(
    project_root: Path,
    platforms: list[str],
    relogin: bool,
    notify_wechat: bool,
    timeout: int,
    write_json: bool,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    expired: list[str] = []

    for platform_name in platforms:
        item = _check_platform(platform_name, project_root)
        if not item["ok"]:
            expired.append(platform_name)
            if relogin:
                relogin_ok, relogin_message = _trigger_relogin(
                    platform_name,
                    timeout=timeout,
                    notify_wechat=notify_wechat,
                )
                item["relogin_triggered"] = True
                item["relogin_message"] = relogin_message
                item["relogin_request_ok"] = relogin_ok
            else:
                item["relogin_triggered"] = False
        else:
            item["relogin_triggered"] = False
        results.append(item)

    now = datetime.now().astimezone()
    summary = {
        "checked_at": now.isoformat(),
        "project_root": str(project_root),
        "all_valid": not expired,
        "expired_platforms": expired,
        "results": results,
    }

    if write_json:
        out_dir = project_root / "logs" / "login_monitor"
        out_dir.mkdir(parents=True, exist_ok=True)
        latest = out_dir / "latest.json"
        history = out_dir / f"status_{now.strftime('%Y%m%d_%H%M%S')}.json"
        text = json.dumps(summary, ensure_ascii=False, indent=2)
        latest.write_text(text, encoding="utf-8")
        history.write_text(text, encoding="utf-8")
        summary["output_file"] = str(history)
        summary["latest_file"] = str(latest)

    return summary


def _print_summary(summary: dict[str, Any]) -> None:
    checked_at = summary["checked_at"]
    print("=" * 60)
    print(f"[LOGIN-MONITOR] 检查时间: {checked_at}")
    print(f"[LOGIN-MONITOR] 项目目录: {summary['project_root']}")
    print("-" * 60)
    for item in summary["results"]:
        prefix = "[OK]" if item["ok"] else "[EXPIRED]"
        print(f"{prefix} {item['label']} ({item['platform']}): {item['message']}")
        if item.get("relogin_triggered"):
            print(f"      -> 已触发重新登录: {item.get('relogin_message', '')}")
    print("-" * 60)
    if summary["all_valid"]:
        print("[SUMMARY] 四个平台登录状态正常")
    else:
        labels = [AUTH.PLATFORMS[name]["label"] for name in summary["expired_platforms"]]
        print(f"[SUMMARY] 登录失效平台: {', '.join(labels)}")
    if summary.get("output_file"):
        print(f"[SUMMARY] 结果已保存: {summary['output_file']}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="四平台登录状态巡检器")
    parser.add_argument(
        "--project-root",
        default="",
        help="项目根目录；默认使用当前仓库根目录",
    )
    parser.add_argument(
        "--platform",
        action="append",
        choices=["all", *AUTH.PLATFORMS.keys()],
        help="指定检查平台；可重复传入，默认 all",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="轮询间隔秒数；0 表示只执行一次",
    )
    parser.add_argument(
        "--trigger-relogin",
        action="store_true",
        help="发现登录失效时，自动打开对应平台登录页",
    )
    parser.add_argument(
        "--notify-wechat",
        action="store_true",
        help="与 --trigger-relogin 一起使用；自动把二维码发到微信",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="传给登录脚本的超时时间（秒）",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="不写入 logs/login_monitor/*.json",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=0,
        help="轮询模式下最多执行几轮；0 表示无限",
    )
    args = parser.parse_args()

    if args.notify_wechat and not args.trigger_relogin:
        parser.error("--notify-wechat 必须和 --trigger-relogin 一起使用")
    if args.interval < 0:
        parser.error("--interval 不能小于 0")
    if args.max_rounds < 0:
        parser.error("--max-rounds 不能小于 0")

    project_root = _project_root(args.project_root)
    platforms = _normalize_platforms(args.platform)

    round_no = 0
    exit_code = 0
    while True:
        round_no += 1
        summary = _run_once(
            project_root=project_root,
            platforms=platforms,
            relogin=args.trigger_relogin,
            notify_wechat=args.notify_wechat,
            timeout=args.timeout,
            write_json=not args.no_json,
        )
        _print_summary(summary)
        if not summary["all_valid"]:
            exit_code = 2

        if args.interval == 0:
            break
        if args.max_rounds and round_no >= args.max_rounds:
            break
        time.sleep(args.interval)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
