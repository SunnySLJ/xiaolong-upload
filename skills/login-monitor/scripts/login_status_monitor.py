#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定时巡检视频号登录状态，并在失效时触发重新登录流程。"""
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

ensure_preferred_python_3_11()


SKILL_ROOT = Path(__file__).resolve().parents[1]
AUTH_SCRIPT = SKILL_ROOT.parent / "auth" / "scripts" / "platform_login.py"
STATE_FILE = SKILL_ROOT / "login_monitor_state.json"
DEFAULT_MAX_RELOGIN_PER_DAY = 5


def _load_auth_module():
    spec = importlib.util.spec_from_file_location("skill_auth_platform_login", AUTH_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 auth 脚本: {AUTH_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUTH = _load_auth_module()
CLI_PLATFORMS = ("shipinhao",)
# 巡检脚本当前只支持视频号；不要在这里追加其它平台，除非 auth skill 先恢复对应检查能力。


def _project_root(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    return SKILL_ROOT.parents[1]


def _normalize_platforms(values: list[str] | None) -> list[str]:
    if not values or values == ["all"]:
        return list(CLI_PLATFORMS)
    result: list[str] = []
    for item in values:
        if item == "all":
            return list(CLI_PLATFORMS)
        if item not in CLI_PLATFORMS:
            raise ValueError(f"未知平台: {item}")
        if item not in result:
            result.append(item)
    return result


def _status_label(ok: bool) -> str:
    return "valid" if ok else "expired"


def _load_state() -> dict[str, Any]:
    today = datetime.now().astimezone().date().isoformat()
    if not STATE_FILE.exists():
        return {"date": today, "relogin_counts": {}}
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"date": today, "relogin_counts": {}}
    if state.get("date") != today:
        return {"date": today, "relogin_counts": {}}
    counts = state.get("relogin_counts", {})
    if not isinstance(counts, dict):
        counts = {}
    return {"date": today, "relogin_counts": counts}


def _save_state(state: dict[str, Any]) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    project_root: Path,
    timeout: int,
    notify_wechat: bool,
) -> tuple[bool, str]:
    del timeout
    cfg = AUTH.PLATFORMS[platform_name]
    if not AUTH.is_port_listening(cfg["port"]):
        try:
            AUTH.launch_connect_chrome(platform_name, project_root)
        except Exception as exc:
            return False, f"{cfg['label']} 启动 Chrome 失败: {exc}"
        deadline = time.time() + 20
        while time.time() < deadline:
            if AUTH.is_port_listening(cfg["port"]):
                break
            time.sleep(0.25)
        else:
            return False, f"{cfg['label']} connect 端口 {cfg['port']} 启动超时"

    AUTH.open_target_tab(platform_name)
    time.sleep(1)
    screenshot_path = AUTH.capture_login_screenshot(platform_name, project_root)
    if screenshot_path and notify_wechat:
        sent = AUTH.send_wechat_notification(platform_name, screenshot_path)
        if sent:
            return True, f"{cfg['label']} 登录页已打开，二维码已发送到微信: {screenshot_path}"
        return False, f"{cfg['label']} 登录页已打开，但二维码发送到微信失败: {screenshot_path}"
    if screenshot_path:
        return True, f"{cfg['label']} 登录页已打开，二维码已保存: {screenshot_path}"
    return True, f"{cfg['label']} 登录页已打开，但本次未提取到二维码图片"


def _run_once(
    project_root: Path,
    platforms: list[str],
    relogin: bool,
    notify_wechat: bool,
    timeout: int,
    write_json: bool,
    max_relogin_per_day: int,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    expired: list[str] = []
    state = _load_state()

    for platform_name in platforms:
        relogin_count_today = int(state["relogin_counts"].get(platform_name, 0))
        if relogin and relogin_count_today >= max_relogin_per_day:
            item = {
                "platform": platform_name,
                "label": AUTH.PLATFORMS[platform_name]["label"],
                "ok": False,
                "status": "skipped",
                "message": f"今日已达到 {max_relogin_per_day} 次重登上限，跳过今日检测",
                "relogin_triggered": False,
                "relogin_skipped_today": True,
                "relogin_trigger_count_today": relogin_count_today,
            }
            expired.append(platform_name)
            results.append(item)
            continue

        item = _check_platform(platform_name, project_root)
        item["relogin_trigger_count_today"] = relogin_count_today
        item["relogin_skipped_today"] = False
        if not item["ok"]:
            expired.append(platform_name)
            if relogin:
                state["relogin_counts"][platform_name] = relogin_count_today + 1
                _save_state(state)
                relogin_ok, relogin_message = _trigger_relogin(
                    platform_name,
                    project_root,
                    timeout=timeout,
                    notify_wechat=notify_wechat,
                )
                item["relogin_triggered"] = True
                item["relogin_message"] = relogin_message
                item["relogin_request_ok"] = relogin_ok
                item["relogin_trigger_count_today"] = int(state["relogin_counts"].get(platform_name, 0))
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
        prefix = "[OK]" if item["ok"] else "[SKIPPED]" if item["status"] == "skipped" else "[EXPIRED]"
        print(f"{prefix} {item['label']} ({item['platform']}): {item['message']}")
        if item.get("relogin_triggered"):
            print(f"      -> 已触发重新登录: {item.get('relogin_message', '')}")
        if "relogin_trigger_count_today" in item:
            print(f"      -> 今日已触发: {item['relogin_trigger_count_today']} 次")
    print("-" * 60)
    if summary["all_valid"]:
        print("[SUMMARY] 视频号登录状态正常")
    else:
        labels = [AUTH.PLATFORMS[name]["label"] for name in summary["expired_platforms"]]
        print(f"[SUMMARY] 登录失效平台: {', '.join(labels)}")
    if summary.get("output_file"):
        print(f"[SUMMARY] 结果已保存: {summary['output_file']}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="视频号登录状态巡检器")
    parser.add_argument(
        "--project-root",
        default="",
        help="项目根目录；默认使用当前仓库根目录",
    )
    parser.add_argument(
        "--platform",
        action="append",
        choices=["all", *CLI_PLATFORMS],
        help="指定检查平台；当前仅保留视频号，默认 all",
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
    parser.add_argument(
        "--max-relogin-per-day",
        type=int,
        default=DEFAULT_MAX_RELOGIN_PER_DAY,
        help="单个平台每天最多触发几次重新登录；达到上限后当天跳过",
    )
    args = parser.parse_args()

    if args.notify_wechat and not args.trigger_relogin:
        parser.error("--notify-wechat 必须和 --trigger-relogin 一起使用")
    if args.interval < 0:
        parser.error("--interval 不能小于 0")
    if args.max_rounds < 0:
        parser.error("--max-rounds 不能小于 0")
    if args.max_relogin_per_day < 0:
        parser.error("--max-relogin-per-day 不能小于 0")

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
            max_relogin_per_day=args.max_relogin_per_day,
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
