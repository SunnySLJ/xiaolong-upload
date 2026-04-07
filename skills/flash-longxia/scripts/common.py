#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flash-longxia skill 共享运行时辅助函数。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resolve_repo_root() -> Path | None:
    """优先从 cwd、环境变量和 OpenClaw 常见目录定位仓库。"""
    candidates: list[Path] = []

    env_root = os.environ.get("OPENCLAW_UPLOAD_ROOT")
    if env_root:
        candidates.append(Path(env_root).expanduser())

    cwd = Path.cwd().resolve()
    candidates.extend([cwd, *cwd.parents])

    script_dir = Path(__file__).resolve().parent
    candidates.extend([script_dir, *script_dir.parents])

    home = Path.home()
    candidates.extend([
        home / ".openclaw" / "workspace" / "openclaw_upload",
        home / "Desktop" / "openclaw_upload",
        home / "workspace" / "openclaw_upload",
        home / "openclaw_upload",
    ])

    for candidate in candidates:
        try:
            candidate = candidate.resolve()
        except FileNotFoundError:
            continue

        workflow = candidate / "flash_longxia" / "zhenlongxia_workflow.py"
        if workflow.exists():
            return candidate
    return None


def resolve_venv_python(repo_root: Path) -> Path | None:
    """兼容 macOS/Linux 与 Windows 的虚拟环境 Python。"""
    venv_root = repo_root / ".venv"
    candidates = [
        venv_root / "bin" / "python3.12",
        venv_root / "bin" / "python3",
        venv_root / "bin" / "python",
        venv_root / "Scripts" / "python.exe",
        venv_root / "Scripts" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def ensure_project_python(repo_root: Path) -> None:
    """优先切换到仓库内的 .venv Python，未命中则继续使用当前解释器。"""
    venv_python = resolve_venv_python(repo_root)
    if venv_python is None:
        return

    if Path(sys.prefix).resolve() == (repo_root / ".venv").resolve():
        return

    os.execv(str(venv_python), [str(venv_python), *sys.argv])
