#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Upload Desktop\\2.mp4 to Douyin / XHS / Kuaishou / Shipinhao with generated copy."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = Path(__file__).resolve().parent

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from common.console import ensure_console_ready, safe_print

ensure_console_ready()

# Per platform limits:
# DY title<=30; XHS title<=20 tags<=5; KS title<=15 tags<=4; SPH title<=64 tags<=10
JOBS: list[tuple[str, str, str, str, str]] = [
    (
        "upload_douyin_connect.ps1",
        "今日份生活小记录",
        "把今天的片段收进这支小视频里，平凡里也有一点甜。愿你看完能放松片刻，评论区聊聊你的感受～",
        "生活记录,日常分享,美好时光,vlog",
        "抖音",
    ),
    (
        "upload_xiaohongshu_connect.ps1",
        "今日份生活小记录",
        "把今天的片段收进这支小视频里，平凡里也有一点甜。愿你看完能放松片刻，评论区聊聊你的感受～",
        "生活记录,日常分享,美好时光,vlog,小确幸",
        "小红书",
    ),
    (
        "upload_kuaishou_connect.ps1",
        "记录生活小确幸",
        "把今天的片段剪成短视频，记录平凡里的小美好。喜欢的话点个赞～",
        "生活记录,日常分享,美好时光,vlog",
        "快手",
    ),
    (
        "upload_shipinhao_connect.ps1",
        "今日份生活小记录｜随心剪的一段",
        "把今天的片段收进这支视频里，平凡日子也值得被记录。感谢观看，欢迎互动留言。",
        "生活记录,日常分享,美好时光,vlog,小确幸,随手拍",
        "视频号",
    ),
]


def main() -> int:
    video = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Desktop" / "2.mp4"
    if not video.is_file():
        safe_print(f"视频不存在: {video}")
        return 1

    safe_print("生成内容（四平台，含抖音优先）：", flush=True)
    for _, title, desc, tags, label in JOBS:
        safe_print(f"  [{label}] 标题: {title}", flush=True)
        safe_print(f"  [{label}] 文案: {desc}", flush=True)
        safe_print(f"  [{label}] 标签: {tags}", flush=True)
        safe_print(flush=True)
    safe_print(f"视频: {video}\n", flush=True)

    # 强制 UTF-8，避免 PowerShell + 中文参数在部分终端下乱码。
    env = dict(**__import__("os").environ)
    env["PYTHONIOENCODING"] = "utf-8"

    # 串行执行：前一个平台完成后再进入下一个平台，便于排查与重试。
    for ps1, title, desc, tags, label in JOBS:
        script = _SCRIPTS / ps1
        safe_print(f"========== [{label}] ==========")
        r = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                str(video.resolve()),
                title,
                desc,
                tags,
            ],
            cwd=str(_ROOT),
            env=env,
        )
        if r.returncode != 0:
            safe_print(f"[{label}] 退出码 {r.returncode}")
        safe_print()

    safe_print("四平台队列已跑完（抖音 -> 小红书 -> 快手 -> 视频号）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
