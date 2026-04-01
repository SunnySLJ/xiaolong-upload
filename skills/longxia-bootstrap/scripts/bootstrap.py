#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform as sys_platform
import shlex
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = SKILL_ROOT / "project_config.json"
ALLOWED_PLATFORMS = ("shipinhao",)
REQUIRED_FILES = (
    "upload.py",
    "requirements.txt",
    "skills/auth/scripts/platform_login.py",
)


def _is_windows() -> bool:
    return sys_platform.system() == "Windows"


def _python_candidates() -> list[list[str]]:
    candidates: list[list[str]] = []
    config = _load_config()
    configured = str(config.get("python_cmd", "")).strip()
    if configured:
        candidates.append(shlex.split(configured, posix=not _is_windows()))
    env_cmd = os.environ.get("LONGXIA_PYTHON_CMD", "").strip()
    if env_cmd:
        candidates.append(shlex.split(env_cmd, posix=not _is_windows()))
    if sys.version_info[:2] == (3, 12):
        candidates.append([sys.executable])
    if _is_windows():
        candidates.extend(
            [
                ["py", "-3.12"],
                [r"C:\Python312\python.exe"],
                [str(Path.home() / "AppData/Local/Programs/Python/Python312/python.exe")],
            ]
        )
    else:
        candidates.extend(
            [
                ["/opt/homebrew/bin/python3.12"],
                ["/opt/homebrew/opt/python@3.12/bin/python3.12"],
                ["python3.12"],
            ]
        )
    deduped: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for candidate in candidates:
        key = tuple(candidate)
        if not candidate or key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _probe_python(cmd: list[str]) -> bool:
    try:
        result = subprocess.run(
            cmd + ["-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
            text=True,
            capture_output=True,
            check=True,
        )
    except Exception:
        return False
    return (result.stdout or "").strip() == "3.12"


def get_python_cmd() -> list[str]:
    for cmd in _python_candidates():
        if _probe_python(cmd):
            return cmd
    sample = (
        "/opt/homebrew/bin/python3.12"
        if not _is_windows()
        else r"py -3.12"
    )
    raise SystemExit(f"未找到可用的 Python 3.12。先执行 set-python，示例: {sample}")


def _python_cmd_str(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def _load_config() -> dict:
    if CONFIG_PATH.is_file():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_config(data: dict) -> None:
    CONFIG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _candidate_roots() -> list[Path]:
    seen: set[str] = set()
    candidates: list[Path] = []
    for raw in (
        os.environ.get("XIAOLONG_UPLOAD_ROOT", ""),
        _load_config().get("project_root", ""),
        str(Path.cwd()),
        str(Path.home() / ".openclaw" / "workspace" / "xiaolong-upload"),
        str(Path.home() / "Desktop" / "xiaolong-upload"),
        str(Path.home() / "source" / "xiaolong-upload"),
        r"C:\Users\Public\xiaolong-upload" if _is_windows() else "",
    ):
        if not raw:
            continue
        path = Path(raw).expanduser().resolve()
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(path)
    return candidates


def _is_project_root(path: Path) -> bool:
    return all((path / rel).exists() for rel in REQUIRED_FILES)


def find_project_root() -> Path | None:
    for path in _candidate_roots():
        if _is_project_root(path):
            return path
    return None


def ensure_project_root() -> Path:
    root = find_project_root()
    if root is None:
        raise SystemExit(
            "未找到 xiaolong-upload 项目根目录。先执行: "
            f"{Path(__file__).resolve()} set-root /abs/path/to/xiaolong-upload"
        )
    return root


def ensure_python() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"必须使用 Python 3.12 运行，当前是 {sys.executable}")


def _run(cmd: list[str], cwd: Path) -> int:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(cmd, cwd=str(cwd), env=env)
    return int(result.returncode)


def _capture(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        check=check,
    )


def cmd_status(_: argparse.Namespace) -> int:
    ensure_python()
    root = find_project_root()
    config = _load_config()
    python_cmd = get_python_cmd()
    print(f"python: {sys.executable}")
    print(f"python_cmd: {_python_cmd_str(python_cmd)}")
    print(f"config: {CONFIG_PATH}")
    print(f"configured_project_root: {config.get('project_root', '')}")
    print(f"configured_python_cmd: {config.get('python_cmd', '')}")
    print(f"detected_project_root: {root or ''}")
    if root is None:
        print("project_status: missing")
        return 1
    print("project_status: ok")
    missing = [rel for rel in REQUIRED_FILES if not (root / rel).exists()]
    if missing:
        print("missing_files:", ", ".join(missing))
        return 1
    check_cmd = python_cmd + [
        "-c",
        "import websockets, nodriver, loguru, pyautogui; print('dependencies: ok')",
    ]
    return _run(check_cmd, root)


def cmd_set_root(args: argparse.Namespace) -> int:
    ensure_python()
    root = Path(args.project_root).expanduser().resolve()
    if not _is_project_root(root):
        print(f"不是有效项目根目录: {root}")
        return 1
    config = _load_config()
    config["project_root"] = str(root)
    _save_config(config)
    print(f"project_root 已保存: {root}")
    return 0


def cmd_set_python(args: argparse.Namespace) -> int:
    ensure_python()
    raw = " ".join(args.python_cmd).strip()
    cmd = shlex.split(raw, posix=not _is_windows())
    if not _probe_python(cmd):
        print(f"不是可用的 Python 3.12 命令: {raw}")
        return 1
    config = _load_config()
    config["python_cmd"] = raw
    _save_config(config)
    print(f"python_cmd 已保存: {raw}")
    return 0


def cmd_install_deps(_: argparse.Namespace) -> int:
    ensure_python()
    root = ensure_project_root()
    python_cmd = get_python_cmd()
    pip_cmd = python_cmd + ["-m", "pip", "install"]
    if _is_windows():
        pip_cmd += ["-r", "requirements.txt"]
    else:
        pip_cmd += ["--user", "--break-system-packages", "-r", "requirements.txt"]
    return _run(
        pip_cmd,
        root,
    )


def cmd_sync(_: argparse.Namespace) -> int:
    ensure_python()
    root = ensure_project_root()
    git_dir = root / ".git"
    if not git_dir.exists():
        print(f"不是 git 仓库，无法同步源码: {root}")
        return 1

    status = _capture(["git", "status", "--short"], root)
    dirty_lines = [line for line in (status.stdout or "").splitlines() if line.strip()]
    if dirty_lines:
        print("工作区存在未提交改动，已停止同步。")
        for line in dirty_lines[:20]:
            print(line)
        if len(dirty_lines) > 20:
            print(f"... 还有 {len(dirty_lines) - 20} 行未显示")
        return 1

    branch = _capture(["git", "branch", "--show-current"], root).stdout.strip()
    before = _capture(["git", "rev-parse", "HEAD"], root).stdout.strip()
    pull = _capture(["git", "pull", "--ff-only"], root, check=False)
    if pull.returncode != 0:
        print("git pull --ff-only 失败。")
        if pull.stdout.strip():
            print(pull.stdout.strip())
        if pull.stderr.strip():
            print(pull.stderr.strip())
        return int(pull.returncode or 1)

    after = _capture(["git", "rev-parse", "HEAD"], root).stdout.strip()
    print(f"branch: {branch}")
    print(f"before: {before}")
    print(f"after:  {after}")
    print((pull.stdout or "").strip() or "Already up to date.")

    deps_rc = cmd_install_deps(argparse.Namespace())
    if deps_rc != 0:
        print("源码已同步，但依赖安装失败。")
        return deps_rc

    log = _capture(["git", "log", "--oneline", "-1"], root)
    if log.stdout.strip():
        print(f"latest_commit: {log.stdout.strip()}")
    return 0


def _ensure_platform(platform: str) -> str:
    if platform not in ALLOWED_PLATFORMS:
        raise SystemExit(f"当前 bootstrap 入口只允许: {', '.join(ALLOWED_PLATFORMS)}")
    return platform


def cmd_login_check(args: argparse.Namespace) -> int:
    ensure_python()
    root = ensure_project_root()
    platform = _ensure_platform(args.platform)
    cmd = get_python_cmd() + [
        "skills/auth/scripts/platform_login.py",
        "--project-root",
        str(root),
        "--platform",
        platform,
        "--check-only",
    ]
    return _run(cmd, root)


def cmd_login(args: argparse.Namespace) -> int:
    ensure_python()
    root = ensure_project_root()
    platform = _ensure_platform(args.platform)
    cmd = get_python_cmd() + [
        "skills/auth/scripts/platform_login.py",
        "--project-root",
        str(root),
        "--platform",
        platform,
    ]
    if args.notify_wechat:
        cmd.append("--notify-wechat")
    return _run(cmd, root)


def cmd_upload(args: argparse.Namespace) -> int:
    ensure_python()
    root = ensure_project_root()
    platform = _ensure_platform(args.platform)
    cmd = get_python_cmd() + [
        "upload.py",
        "--platform",
        platform,
        args.video_path,
        args.title,
        args.description,
        args.tags,
    ]
    if args.login_only:
        cmd.append("--login-only")
    return _run(cmd, root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="longxia bootstrap wrapper")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="检查项目根目录、Python 和依赖")
    status.set_defaults(func=cmd_status)

    set_root = sub.add_parser("set-root", help="保存项目根目录")
    set_root.add_argument("project_root")
    set_root.set_defaults(func=cmd_set_root)

    set_python = sub.add_parser("set-python", help="保存 Python 3.12 命令")
    set_python.add_argument("python_cmd", nargs="+")
    set_python.set_defaults(func=cmd_set_python)

    install = sub.add_parser("install-deps", help="安装项目依赖")
    install.set_defaults(func=cmd_install_deps)

    sync = sub.add_parser("sync", help="同步项目仓库最新代码并补依赖")
    sync.set_defaults(func=cmd_sync)

    login_check = sub.add_parser("login-check", help="检查视频号登录")
    login_check.add_argument("--platform", default="shipinhao", choices=ALLOWED_PLATFORMS)
    login_check.set_defaults(func=cmd_login_check)

    login = sub.add_parser("login", help="打开视频号登录")
    login.add_argument("--platform", default="shipinhao", choices=ALLOWED_PLATFORMS)
    login.add_argument("--notify-wechat", action="store_true")
    login.set_defaults(func=cmd_login)

    upload = sub.add_parser("upload", help="发布视频号")
    upload.add_argument("--platform", default="shipinhao", choices=ALLOWED_PLATFORMS)
    upload.add_argument("video_path")
    upload.add_argument("title", nargs="?", default="")
    upload.add_argument("description", nargs="?", default="")
    upload.add_argument("tags", nargs="?", default="")
    upload.add_argument("--login-only", action="store_true")
    upload.set_defaults(func=cmd_upload)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
