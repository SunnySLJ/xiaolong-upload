#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Thin wrapper around the auth skill login helper.

Keep a single source of truth in skills/auth/scripts/platform_login.py to
avoid drift between project and skill entrypoints.

Current project policy: login checking/relogin is only exposed for Shipinhao.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTH_SCRIPT = PROJECT_ROOT / "skills" / "auth" / "scripts" / "platform_login.py"


def _load_auth_module():
    spec = importlib.util.spec_from_file_location("project_platform_login_bridge", AUTH_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 auth 登录脚本: {AUTH_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_AUTH = _load_auth_module()


def _default_root() -> Path:
    env_root = (os.environ.get("OPENCLAW_UPLOAD_ROOT") or "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    return PROJECT_ROOT.resolve()


def check_platform_login(platform_name: str, root: Path | None = None, passive: bool = False):
    actual_root = (root or _default_root()).resolve()
    _AUTH._PROJECT_ROOT_OVERRIDE = actual_root
    return _AUTH.check_platform_login(platform_name, actual_root, passive=passive)


def ensure_platform_login(
    platform_name: str,
    wait: bool = True,
    timeout: int = 300,
    notify_wechat: bool = False,
    root: Path | None = None,
):
    actual_root = (root or _default_root()).resolve()
    _AUTH._PROJECT_ROOT_OVERRIDE = actual_root
    return _AUTH.ensure_platform_login(
        platform_name,
        timeout=timeout,
        notify_wechat=notify_wechat,
    ) if wait else _AUTH.ensure_platform_login(
        platform_name,
        timeout=timeout,
        notify_wechat=notify_wechat,
    )


def __getattr__(name: str):
    return getattr(_AUTH, name)


def _main() -> int:
    _AUTH._PROJECT_ROOT_OVERRIDE = _default_root()
    return _AUTH._main()


if __name__ == "__main__":
    raise SystemExit(_main())
