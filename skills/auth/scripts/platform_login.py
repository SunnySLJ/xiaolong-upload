#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-platform connect-login helper for the four upload platforms.

This copy lives inside the auth skill so it can be reused independently.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform as sys_platform
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import websockets

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from common.python_runtime import ensure_preferred_python_3_11

ensure_preferred_python_3_11()


PLATFORMS = {
    "douyin": {
        "label": "抖音",
        "port": 9224,
        "profile_dir": "chrome_connect_dy",
        "url": "https://creator.douyin.com/creator-micro/content/upload",
        "ready_markers": (
            "creator.douyin.com/creator-micro/content/upload",
            "creator.douyin.com/creator-micro/home",
        ),
        "login_markers": ("login", "passport", "扫码登录", "手机号登录"),
        "qr_switch_texts": ("扫码登录",),
        "required_cookie_names": (
            "sessionid",
            "sessionid_ss",
            "sid_tt",
            "uid_tt",
            "sid_guard",
        ),
        "required_cookie_hits": 2,
    },
    "xiaohongshu": {
        "label": "小红书",
        "port": 9223,
        "profile_dir": "chrome_connect_xhs",
        "url": "https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video",
        "ready_markers": (
            "creator.xiaohongshu.com/publish/publish",
            "creator.xiaohongshu.com/creator/home",
            "creator.xiaohongshu.com/publish/notemanager",
            "creator.xiaohongshu.com/content/upload",
        ),
        "login_markers": ("login", "短信登录", "扫码登录"),
        "qr_switch_texts": ("扫码登录",),
        "required_cookie_names": (
            "galaxy_creator_session_id",
            "access-token-creator.xiaohongshu.com",
            "galaxy.creator.beaker.session.id",
            "customer-sso-sid",
            "x-user-id-creator.xiaohongshu.com",
        ),
        "required_cookie_hits": 2,
    },
    "kuaishou": {
        "label": "快手",
        "port": 9225,
        "profile_dir": "chrome_connect_ks",
        "url": "https://cp.kuaishou.com/article/publish/video",
        "ready_markers": (
            "cp.kuaishou.com/article/publish/video",
            "cp.kuaishou.com/article/publish",
            "cp.kuaishou.com/home",
        ),
        "login_markers": ("login", "passport", "扫码登录"),
        "qr_switch_texts": ("扫码登录",),
        "required_cookie_names": (
            "kuaishou.web.cp.api_st",
            "kuaishou.web.cp.api_ph",
            "userId",
            "bUserId",
        ),
        "required_cookie_hits": 2,
    },
    "shipinhao": {
        "label": "视频号",
        "port": 9226,
        "profile_dir": "chrome_connect_sph",
        "url": "https://channels.weixin.qq.com/platform/post/create",
        "ready_markers": ("channels.weixin.qq.com/platform/post/create",),
        "login_markers": ("login", "mp.weixin.qq.com", "微信扫码", "扫码登录"),
        "qr_switch_texts": (),
        "required_cookie_names": (
            "sessionid",
            "wxuin",
        ),
        "required_cookie_hits": 2,
    },
}

# 本地登录检查入口当前只保留视频号；其他平台实现先保留，不在入口暴露。
CLI_PLATFORMS = (
    # "douyin",
    # "xiaohongshu",
    # "kuaishou",
    "shipinhao",
)

_PROJECT_ROOT_OVERRIDE: Path | None = None


def project_root() -> Path:
    return _PROJECT_ROOT_OVERRIDE or Path(__file__).resolve().parents[3]


def chrome_path() -> str:
    env_path = os.environ.get("LOCAL_CHROME_PATH")
    if env_path:
        return env_path
    system = sys_platform.system()
    if system == "Darwin":
        return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if system == "Windows":
        for p in (
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ):
            if Path(p).exists():
                return p
        return "chrome"
    return "google-chrome"


def profile_dir_for(platform_name: str, root: Path | None = None) -> Path:
    root = root or project_root()
    return root / "cookies" / PLATFORMS[platform_name]["profile_dir"]


def is_port_listening(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def close_connect_browser(platform_name: str, timeout: float = 8.0) -> bool:
    port = PLATFORMS[platform_name]["port"]
    # 使用 ps 命令查找 Chrome 主进程（不是 renderer 子进程）
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return False
    
    pids = []
    for line in (result.stdout or "").splitlines():
        # 查找包含 remote-debugging-port=PORT 的 Chrome 主进程
        if f"--remote-debugging-port={port}" in line and "Google Chrome.app/Contents/MacOS/Google Chrome" in line:
            # 跳过 Renderer  helper 进程
            if "Helper" in line:
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                pids.append(int(parts[1]))
    
    if not pids:
        return False
    for pid in sorted(set(pids)):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        except Exception:
            return False
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not is_port_listening(port):
            return True
        time.sleep(0.2)
    return not is_port_listening(port)


def _devtools_get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "platform-login-helper"})
    with urllib.request.urlopen(req, timeout=2) as resp:
        return json.loads(resp.read().decode("utf-8"))


def devtools_tabs(port: int) -> list[dict]:
    try:
        return _devtools_get(f"http://127.0.0.1:{port}/json/list")
    except Exception:
        return []


async def _cdp_fetch_cookies(ws_url: str, base_url: str, timeout: float = 5.0) -> list[dict]:
    async with websockets.connect(ws_url, open_timeout=timeout, close_timeout=timeout) as ws:
        req_id = 1
        await ws.send(json.dumps({
            "id": req_id,
            "method": "Network.getCookies",
            "params": {"urls": [base_url]},
        }))
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msg = json.loads(raw)
            if msg.get("id") == req_id:
                return msg.get("result", {}).get("cookies", [])


async def _cdp_runtime_evaluate(ws_url: str, expression: str, timeout: float = 5.0):
    async with websockets.connect(ws_url, open_timeout=timeout, close_timeout=timeout) as ws:
        req_id = 1
        await ws.send(json.dumps({"id": req_id, "method": "Runtime.enable", "params": {}}))
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msg = json.loads(raw)
            if msg.get("id") == req_id:
                break
        req_id = 2
        await ws.send(json.dumps({
            "id": req_id,
            "method": "Runtime.evaluate",
            "params": {"expression": expression, "returnByValue": True},
        }))
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msg = json.loads(raw)
            if msg.get("id") == req_id:
                return msg.get("result", {}).get("result", {}).get("value")


def _has_required_login_cookies(platform_name: str, tab: dict, base_url: str | None = None) -> bool:
    cfg = PLATFORMS[platform_name]
    cookie_names = tuple(cfg.get("required_cookie_names", ()))
    min_hits = int(cfg.get("required_cookie_hits", 0) or 0)
    if not cookie_names or min_hits <= 0:
        return True
    ws_url = tab.get("webSocketDebuggerUrl") or ""
    cookie_url = base_url or tab.get("url") or cfg["url"]
    if not ws_url or not cookie_url:
        return False
    try:
        cookies = asyncio.run(_cdp_fetch_cookies(ws_url, cookie_url, timeout=5.0))
    except Exception:
        return False
    names = {
        str(cookie.get("name") or "")
        for cookie in cookies
        if cookie.get("name") and cookie.get("value")
    }
    hits = sum(1 for name in cookie_names if name in names)
    return hits >= min_hits


def _find_reusable_session_by_cookies(platform_name: str, tabs: list[dict]) -> dict | None:
    cfg = PLATFORMS[platform_name]
    page_tabs = [tab for tab in tabs if tab.get("type") == "page"]
    for tab in page_tabs:
        if _has_required_login_cookies(platform_name, tab, base_url=cfg["url"]):
            return tab
    return None


def ensure_page_target(platform_name: str, retries: int = 3, wait_seconds: float = 1.0) -> list[dict]:
    port = PLATFORMS[platform_name]["port"]
    tabs = devtools_tabs(port)
    if any(tab.get("type") == "page" for tab in tabs):
        return tabs
    for _ in range(retries):
        open_target_tab(platform_name)
        time.sleep(wait_seconds)
        tabs = devtools_tabs(port)
        if any(tab.get("type") == "page" for tab in tabs):
            return tabs
    return tabs


def open_target_tab(platform_name: str, force_new: bool = False) -> bool:
    """打开目标平台标签页
    
    :param force_new: 是否强制打开新标签页（即使已有标签页存在）
    """
    port = PLATFORMS[platform_name]["port"]
    tabs = devtools_tabs(port)
    if not force_new and any(tab.get("type") == "page" for tab in tabs):
        return False
    url = PLATFORMS[platform_name]["url"]
    encoded = urllib.parse.quote(url, safe=":/?&=%")
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/json/new?{encoded}",
            method="PUT",
            headers={"User-Agent": "platform-login-helper"},
        )
        with urllib.request.urlopen(req, timeout=3):
            return True
    except urllib.error.HTTPError:
        return False
    except Exception:
        return False


def launch_connect_chrome(platform_name: str, root: Path | None = None) -> None:
    root = root or project_root()
    cfg = PLATFORMS[platform_name]
    profile_dir = profile_dir_for(platform_name, root)
    profile_dir.mkdir(parents=True, exist_ok=True)
    system = sys_platform.system()
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if system == "Darwin":
        args = [
            "open",
            "-na",
            "Google Chrome",
            "--args",
            f"--remote-debugging-port={cfg['port']}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile_dir}",
            "--start-maximized",
            cfg["url"],
        ]
        kwargs["start_new_session"] = True
    else:
        args = [
            chrome_path(),
            f"--remote-debugging-port={cfg['port']}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile_dir}",
            "--start-maximized",
            cfg["url"],
        ]
        if system == "Windows":
            kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0)
        else:
            kwargs["start_new_session"] = True
    subprocess.Popen(args, **kwargs)


def send_wechat_notification(platform_name: str, screenshot_path: str) -> bool:
    label = PLATFORMS[platform_name]["label"]
    if not os.path.exists(screenshot_path):
        return False
    try:
        # 使用 openclaw message 命令发送图片到微信
        # 注意：需要指定 target 参数
        cmd = [
            "openclaw",
            "message",
            "send",
            "--channel",
            "openclaw-weixin",
            "--target",
            "o9cq80zNpOiKXmKuyo7jrp0WpX9Y@im.wechat",
            "--message",
            f"🔔 {label}登录已过期。请打开图片扫码登录，登录成功后系统会继续等待并恢复发布。",
            "--media",
            screenshot_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"{label} 登录二维码已发送到微信")
            return True
        else:
            print(f"{label} 发送失败：{result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"{label} 发送异常：{e}")
        return False


def _extract_qr_image_via_cdp(platform_name: str, output_path: str) -> str | None:
    cfg = PLATFORMS[platform_name]
    page_tabs = [tab for tab in devtools_tabs(cfg["port"]) if tab.get("type") == "page"]
    if not page_tabs:
        return None

    def tab_rank(tab: dict) -> int:
        url = (tab.get("url") or "").lower()
        if platform_name == "douyin":
            if "/login" in url:
                return 0
            if "creator.douyin.com" in url:
                return 1
        if platform_name == "kuaishou":
            if "passport.kuaishou.com" in url:
                return 0
            if "cp.kuaishou.com" in url:
                return 1
        if platform_name == "shipinhao":
            if "login-for-iframe" in url:
                return 0
            if url.endswith("/login.html"):
                return 1
            if "channels.weixin.qq.com" in url:
                return 2
        return 10

    page_tabs.sort(key=tab_rank)
    if platform_name == "douyin":
        douyin_script = r"""
const fs = require("fs");
const wsUrl = process.argv[1];
const outputPath = process.argv[2];
const ws = new WebSocket(wsUrl);
let id = 0;
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const msgId = ++id;
    const onMessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.id === msgId) {
        ws.removeEventListener("message", onMessage);
        if (data.error) reject(data.error);
        else resolve(data.result);
      }
    };
    ws.addEventListener("message", onMessage);
    ws.send(JSON.stringify({ id: msgId, method, params }));
  });
}
ws.addEventListener("open", async () => {
  try {
    await send("Runtime.enable");
    await send("Page.enable");
    const expr = `(() => {
      const text = document.body.innerText || '';
      const onLoginPage = /扫码登录|手机号登录|验证码登录|登录抖音创作者中心/.test(text);
      if (!onLoginPage) {
        return { kind: 'not-login-page' };
      }
      if (!/扫码登录/.test(text)) {
        const scanTab = [...document.querySelectorAll('div,span,button,a,p')].find(el =>
          (el.innerText || el.textContent || '').trim() === '扫码登录'
        );
        if (scanTab) {
          scanTab.click();
          return { kind: 'retry-needed', waitMs: 1200 };
        }
      }
      if (/已失效|二维码失效|二维码已失效/.test(text)) {
        const retry = [...document.querySelectorAll('button,div,span,a,p')].find(el =>
          /刷新|重新获取|重新加载/.test((el.innerText || el.textContent || '').trim())
        );
        if (retry) {
          retry.click();
          return { kind: 'retry-needed', waitMs: 1200 };
        }
      }
      const primary = Array.from(document.querySelectorAll('img[class*=qrcode_img]'));
      const fallback = Array.from(document.images).filter(img =>
        (img.src || '').startsWith('data:image/') && img.naturalWidth >= 180 && img.naturalHeight >= 180
      );
      const candidates = [...primary, ...fallback];
      const uniq = [];
      const seen = new Set();
      for (const img of candidates) {
        const key = (img.currentSrc || img.src || '') + '|' + String(img.className || '');
        if (!seen.has(key)) {
          seen.add(key);
          uniq.push(img);
        }
      }
      const img = uniq
        .map(img => {
          const rect = img.getBoundingClientRect();
          const cls = String(img.className || '');
          let score = 0;
          if (/qrcode_img/.test(cls)) score += 100;
          if ((img.src || '').startsWith('data:image/png')) score += 30;
          if (img.naturalWidth >= 256 && img.naturalHeight >= 256) score += 20;
          if (rect.width >= 180 && rect.height >= 180) score += 20;
          return { img, rect, score };
        })
        .sort((a, b) => b.score - a.score)[0];
      if (!img) {
        if (/如何扫码|打开「抖音APP」/.test(text)) {
          return { kind: 'retry-needed', waitMs: 1500 };
        }
        return null;
      }
      const rect = img.rect;
      const src = img.img.currentSrc || img.img.src || '';
      if (!src) {
        return { kind: 'retry-needed', waitMs: 1500 };
      }
      if (src.startsWith('data:image/svg+xml')) {
        return {
          kind: 'clip',
          rect: { x: rect.left, y: rect.top, width: rect.width, height: rect.height }
        };
      }
      if (src.startsWith('data:image/')) {
        return { kind: 'data-url', payload: src };
      }
      return null;
    })()`;
    let attempts = 0;
    while (attempts < 20) {
      let result = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
      let value = result?.result?.value || null;
      if (value && value.kind === "data-url" && typeof value.payload === "string") {
        fs.writeFileSync(outputPath, Buffer.from(value.payload.split(",")[1], "base64"));
        process.exit(0);
      }
      if (value && value.kind === "clip" && value.rect) {
        const pad = 24;
        const clip = {
          x: Math.max(0, Number(value.rect.x || 0) - pad),
          y: Math.max(0, Number(value.rect.y || 0) - pad),
          width: Math.max(120, Number(value.rect.width || 0) + pad * 2),
          height: Math.max(120, Number(value.rect.height || 0) + pad * 2),
          scale: 1,
        };
        const shot = await send("Page.captureScreenshot", {
          format: "png",
          fromSurface: true,
          clip,
        });
        const data = shot?.data || "";
        if (data) {
          fs.writeFileSync(outputPath, Buffer.from(data, "base64"));
          process.exit(0);
        }
      }
      if (value && value.kind === "not-login-page") {
        process.exit(2);
      }
      if (value && value.kind === "retry-needed") {
        await new Promise((resolve) => setTimeout(resolve, value.waitMs || 1200));
        attempts += 1;
        continue;
      }
      await new Promise((resolve) => setTimeout(resolve, 1500));
      attempts += 1;
    }
    process.exit(2);
  } catch (err) {
    console.error(String(err));
    process.exit(1);
  } finally {
    ws.close();
  }
});
"""
        for tab in page_tabs:
            ws_url = tab.get("webSocketDebuggerUrl") or ""
            if not ws_url:
                continue
            try:
                subprocess.run(
                    ["node", "-e", douyin_script, ws_url, output_path],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
            except Exception:
                continue
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
        return None
    if platform_name == "xiaohongshu":
        xiaohongshu_script = r"""
const fs = require("fs");
const wsUrl = process.argv[1];
const outputPath = process.argv[2];
const ws = new WebSocket(wsUrl);
let id = 0;
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const msgId = ++id;
    const onMessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.id === msgId) {
        ws.removeEventListener("message", onMessage);
        if (data.error) reject(data.error);
        else resolve(data.result);
      }
    };
    ws.addEventListener("message", onMessage);
    ws.send(JSON.stringify({ id: msgId, method, params }));
  });
}
ws.addEventListener("open", async () => {
  try {
    await send("Runtime.enable");
    const expr = `(() => {
      const box = document.querySelector('.login-box-container') || document;
      const text = box.innerText || document.body.innerText || '';
      const findByText = (pattern) => [...document.querySelectorAll('button,div,span,a,p')].find(el => {
        const value = (el.innerText || el.textContent || '').trim();
        return value && pattern.test(value);
      });
      if ((/短信登录|验证码登录|手机号登录/.test(text)) && !/APP扫一扫登录|扫码/.test(text)) {
        const qrSwitch = document.querySelector('img.css-wemwzq') ||
          findByText(/APP扫一扫登录|扫码登录|扫码/);
        if (qrSwitch) {
          qrSwitch.click();
          return { kind: 'retry-needed', waitMs: 1800 };
        }
      }
      if (/二维码已过期|返回重新扫描/.test(text)) {
        const retry = findByText(/返回重新扫描|刷新二维码|刷新|重新获取/);
        if (retry) {
          retry.click();
          return { kind: 'retry-needed', waitMs: 1500 };
        }
      }
      const score = (img) => {
        const src = img.getAttribute('src') || '';
        const cls = img.className || '';
        let s = 0;
        if (src.startsWith('data:image/')) s += 5;
        if (/qr|qrcode/i.test(cls)) s += 4;
        if (img.naturalWidth >= 180 && img.naturalHeight >= 180) s += 3;
        if (Math.abs(img.naturalWidth - img.naturalHeight) <= 20) s += 2;
        return s;
      };
      const candidates = Array.from(box.querySelectorAll('img')).concat(Array.from(document.images || []));
      const img = candidates
        .filter(img => img && img.naturalWidth >= 120 && img.naturalHeight >= 120)
        .filter(img => !(img.naturalWidth === 128 && img.naturalHeight === 128 && /css-wemwzq/.test(img.className || '')))
        .sort((a, b) => score(b) - score(a))[0];
      if (img && (img.src || '').startsWith('data:image/')) {
        return { kind: 'data-url', payload: img.src };
      }
      if (img && img.getBoundingClientRect) {
        const rect = img.getBoundingClientRect();
        if (rect.width >= 120 && rect.height >= 120) {
          return {
            kind: 'clip',
            rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
          };
        }
      }
      return null;
    })()`;
    let attempts = 0;
    while (attempts < 8) {
      let result = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
      let value = result?.result?.value || null;
      if (value && value.kind === "data-url" && typeof value.payload === "string") {
        fs.writeFileSync(outputPath, Buffer.from(value.payload.split(",")[1], "base64"));
        process.exit(0);
      }
      if (value && value.kind === "clip" && value.rect) {
        const pad = 20;
        const clip = {
          x: Math.max(0, Number(value.rect.x || 0) - pad),
          y: Math.max(0, Number(value.rect.y || 0) - pad),
          width: Math.max(140, Number(value.rect.width || 0) + pad * 2),
          height: Math.max(140, Number(value.rect.height || 0) + pad * 2),
          scale: 1,
        };
        const shot = await send("Page.captureScreenshot", { format: "png", fromSurface: true, clip });
        const data = shot?.data || "";
        if (data) {
          fs.writeFileSync(outputPath, Buffer.from(data, "base64"));
          process.exit(0);
        }
      }
      if (value && value.kind === "retry-needed") {
        await new Promise((resolve) => setTimeout(resolve, value.waitMs || 1500));
        attempts += 1;
        continue;
      }
      await new Promise((resolve) => setTimeout(resolve, 1200));
      attempts += 1;
    }
    process.exit(2);
  } catch (err) {
    console.error(String(err));
    process.exit(1);
  } finally {
    ws.close();
  }
});
"""
        for tab in page_tabs:
            ws_url = tab.get("webSocketDebuggerUrl") or ""
            if not ws_url:
                continue
            try:
                subprocess.run(
                    ["node", "-e", xiaohongshu_script, ws_url, output_path],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
            except Exception:
                continue
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
        return None
    if platform_name == "kuaishou":
        kuaishou_script = r"""
const fs = require("fs");
const wsUrl = process.argv[1];
const outputPath = process.argv[2];
const ws = new WebSocket(wsUrl);
let id = 0;
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const msgId = ++id;
    const onMessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.id === msgId) {
        ws.removeEventListener("message", onMessage);
        if (data.error) reject(data.error);
        else resolve(data.result);
      }
    };
    ws.addEventListener("message", onMessage);
    ws.send(JSON.stringify({ id: msgId, method, params }));
  });
}
ws.addEventListener("open", async () => {
  try {
    await send("Runtime.enable");
    await send("Page.enable");
    const expr = `(() => {
      const text = document.body.innerText || '';
      const collectByText = (pattern) => [...document.querySelectorAll('a,button,[role="button"],div,span,p')]
        .map(el => {
          const value = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
          const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : { width: 0, height: 0 };
          const href = el.href || '';
          const cls = String(el.className || '');
          let score = 0;
          if (!value || !pattern.test(value)) return null;
          if (rect.width >= 20 && rect.height >= 20) score += 20;
          if (value.length <= 8) score += 30;
          if (el.tagName === 'A' || el.tagName === 'BUTTON') score += 40;
          if (href) score += 40;
          if (/login|upload/i.test(cls)) score += 20;
          if (getComputedStyle(el).cursor === 'pointer') score += 10;
          return { el, value, href, score };
        })
        .filter(Boolean)
        .sort((a, b) => b.score - a.score);
      const findActionByText = (pattern) => {
        const items = [...document.querySelectorAll('a,button,[role="button"],div,span,p')]
          .map(el => {
            const value = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
            const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : { width: 0, height: 0 };
            const href = el.href || '';
            const cls = String(el.className || '');
            if (!value || !pattern.test(value)) return null;
            if (value.length > 12) return null;
            let score = 0;
            if (rect.width >= 16 && rect.height >= 16) score += 20;
            if (value.length <= 6) score += 40;
            if (el.tagName === 'A' || el.tagName === 'BUTTON') score += 40;
            if (href) score += 40;
            if (/login|upload|switch|tab|refresh|retry/i.test(cls)) score += 20;
            if (getComputedStyle(el).cursor === 'pointer') score += 10;
            return { el, value, href, score };
          })
          .filter(Boolean)
          .sort((a, b) => b.score - a.score);
        return items.length ? items[0] : null;
      };
      const findByText = (pattern) => {
        const items = collectByText(pattern);
        return items.length ? items[0] : null;
      };
      const clickNode = (node) => {
        if (!node) return false;
        const el = node.el || node;
        try { el.scrollIntoView({ block: 'center', inline: 'center' }); } catch (e) {}
        try { el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true })); } catch (e) {}
        try { el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); } catch (e) {}
        try { el.click(); } catch (e) {}
        try { el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true })); } catch (e) {}
        return true;
      };
      if (!location.href.includes('passport.kuaishou.com')) {
        const loginEntry = findActionByText(/^立即登录$|^去登录$|^登录$/);
        if (loginEntry) {
          if (loginEntry.href && /passport\.kuaishou\.com/.test(loginEntry.href)) {
            location.href = loginEntry.href;
          } else {
            clickNode(loginEntry);
          }
          return { kind: 'retry-needed', waitMs: 1800 };
        }
        const uploadEntry = findActionByText(/^去上传$/);
        if (uploadEntry) {
          if (uploadEntry.href && /passport\.kuaishou\.com/.test(uploadEntry.href)) {
            location.href = uploadEntry.href;
          } else {
            clickNode(uploadEntry);
          }
          return { kind: 'retry-needed', waitMs: 1800 };
        }
      }
      const hasQrCandidate = !!document.querySelector(
        'img[alt="qrcode"], img[class*="qrcode"], img[class*="qr"], canvas[class*="qrcode"], canvas[class*="qr"], [class*="qrcode"] img, [class*="qr"] img'
      );
      if ((/密码登录|验证码登录|手机号登录|短信登录/.test(text)) && !hasQrCandidate) {
        const scanEntry = findActionByText(/^扫码登录$|^APP扫码登录$|^快手APP.*扫码$/) || findByText(/扫码登录|APP扫码登录|快手APP.*扫码/);
        if (scanEntry) {
          clickNode(scanEntry);
          return { kind: 'retry-needed', waitMs: 1500 };
        }
      }
      if (/二维码已失效|二维码过期|点击刷新/.test(text)) {
        const retry = findActionByText(/^点击刷新$|^刷新二维码$|^重新获取$|^点击重试$|^刷新$/) || findByText(/点击刷新|刷新二维码|重新获取|点击重试|刷新/);
        if (retry) {
          clickNode(retry);
          return { kind: 'retry-needed', waitMs: 1200 };
        }
      }

      const scoreImage = (img) => {
        if (!img) return -1;
        const rect = img.getBoundingClientRect ? img.getBoundingClientRect() : { width: 0, height: 0 };
        const src = img.currentSrc || img.src || '';
        const cls = String(img.className || '');
        const alt = String(img.alt || '');
        const parentText = String((img.parentElement && (img.parentElement.innerText || img.parentElement.textContent)) || '');
        let score = 0;
        if (/qrcode|qr-code|qr_code|二维码/i.test(cls)) score += 80;
        if (/qrcode|qr code|二维码/i.test(alt)) score += 60;
        if (/扫码登录|快手APP|二维码/.test(parentText)) score += 40;
        if (src.startsWith('data:image/')) score += 30;
        if (src.startsWith('blob:')) score += 20;
        if (img.naturalWidth >= 160 && img.naturalHeight >= 160) score += 20;
        if (Math.abs(img.naturalWidth - img.naturalHeight) <= 20) score += 10;
        if (rect.width >= 120 && rect.height >= 120) score += 10;
        return score;
      };

      const candidates = [
        ...document.querySelectorAll('img[alt="qrcode"], img[class*="qrcode"], img[class*="qr"], canvas[class*="qrcode"], canvas[class*="qr"]'),
        ...Array.from(document.images || [])
      ];

      const uniq = [];
      const seen = new Set();
      for (const el of candidates) {
        const key = String(el.tagName || '') + '|' + String(el.currentSrc || el.src || '') + '|' + String(el.className || '');
        if (!seen.has(key)) {
          seen.add(key);
          uniq.push(el);
        }
      }

      const best = uniq
        .filter(el => {
          const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
          return rect && rect.width >= 80 && rect.height >= 80;
        })
        .map(el => ({ el, score: scoreImage(el), rect: el.getBoundingClientRect() }))
        .sort((a, b) => b.score - a.score)[0];

      if (!best) {
        if (/扫码登录|快手APP|二维码/.test(text)) {
          return { kind: 'retry-needed', waitMs: 1200 };
        }
        return null;
      }

      const img = best.el;
      if (img.tagName === 'CANVAS') {
        try {
          return { kind: 'data-url', payload: img.toDataURL('image/png') };
        } catch (e) {}
      }

      const src = img.currentSrc || img.src || '';
      if (src.startsWith('data:image/')) {
        return { kind: 'data-url', payload: src };
      }
      if (best.rect && best.rect.width >= 100 && best.rect.height >= 100) {
        return {
          kind: 'clip',
          rect: { x: best.rect.left, y: best.rect.top, width: best.rect.width, height: best.rect.height }
        };
      }
      return null;
    })()`;
    let attempts = 0;
    while (attempts < 10) {
      let result = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
      let value = result?.result?.value || null;
      if (value && value.kind === "data-url" && typeof value.payload === "string") {
        fs.writeFileSync(outputPath, Buffer.from(value.payload.split(",")[1], "base64"));
        process.exit(0);
      }
      if (value && value.kind === "clip" && value.rect) {
        const pad = 20;
        const clip = {
          x: Math.max(0, Number(value.rect.x || 0) - pad),
          y: Math.max(0, Number(value.rect.y || 0) - pad),
          width: Math.max(140, Number(value.rect.width || 0) + pad * 2),
          height: Math.max(140, Number(value.rect.height || 0) + pad * 2),
          scale: 1,
        };
        const shot = await send("Page.captureScreenshot", { format: "png", fromSurface: true, clip });
        const data = shot?.data || "";
        if (data) {
          fs.writeFileSync(outputPath, Buffer.from(data, "base64"));
          process.exit(0);
        }
      }
      if (value && value.kind === "retry-needed") {
        await new Promise((resolve) => setTimeout(resolve, value.waitMs || 1500));
        attempts += 1;
        continue;
      }
      await new Promise((resolve) => setTimeout(resolve, 1200));
      attempts += 1;
    }
    process.exit(2);
  } catch (err) {
    console.error(String(err));
    process.exit(1);
  } finally {
    ws.close();
  }
});
"""
        for tab in page_tabs:
            ws_url = tab.get("webSocketDebuggerUrl") or ""
            if not ws_url:
                continue
            try:
                subprocess.run(
                    ["node", "-e", kuaishou_script, ws_url, output_path],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
            except Exception:
                continue
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
        return None
    if platform_name == "shipinhao":
        shipinhao_script = r"""
const fs = require("fs");
const wsUrl = process.argv[1];
const outputPath = process.argv[2];
const ws = new WebSocket(wsUrl);
let id = 0;
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const msgId = ++id;
    const onMessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.id === msgId) {
        ws.removeEventListener("message", onMessage);
        if (data.error) reject(data.error);
        else resolve(data.result);
      }
    };
    ws.addEventListener("message", onMessage);
    ws.send(JSON.stringify({ id: msgId, method, params }));
  });
}
ws.addEventListener("open", async () => {
  try {
    await send("Runtime.enable");
    await send("Page.enable");
    const expr = `(() => {
      function isVisible(el, win) {
        if (!el || !win) return false;
        const rect = el.getBoundingClientRect();
        if (!rect || rect.width < 80 || rect.height < 80) return false;
        const style = win.getComputedStyle(el);
        if (!style) return false;
        return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      }
      function scoreImage(img, doc) {
        const src = img.currentSrc || img.src || '';
        const cls = ((img.className && String(img.className)) || '').toLowerCase();
        const alt = ((img.alt || '') + ' ' + (img.title || '')).toLowerCase();
        const parentText = ((img.parentElement && img.parentElement.innerText) || doc.body?.innerText || '').slice(0, 1000);
        const rect = img.getBoundingClientRect();
        const ratio = rect.height > 0 ? rect.width / rect.height : 0;
        let score = 0;
        if (/qrcode|qr-code|qr_code|二维码/.test(cls)) score += 80;
        if (/qrcode|qr code|二维码/.test(alt)) score += 40;
        if (/微信扫码|扫码登录|请使用微信扫码/.test(parentText)) score += 30;
        if (src.startsWith('data:image/')) score += 25;
        if (src.startsWith('blob:')) score += 15;
        if (rect.width >= 120 && rect.width <= 420 && rect.height >= 120 && rect.height <= 420) score += 20;
        if (ratio > 0.9 && ratio < 1.1) score += 20;
        if (img.naturalWidth >= 120 && img.naturalHeight >= 120) score += 10;
        return score;
      }
      function scanDoc(doc, offsetX, offsetY, depth, out) {
        if (!doc || depth > 4) return;
        const win = doc.defaultView;
        if (!win) return;
        for (const img of Array.from(doc.images || [])) {
          if (!isVisible(img, win)) continue;
          const rect = img.getBoundingClientRect();
          const score = scoreImage(img, doc);
          if (score < 40) continue;
          out.push({
            score,
            src: img.currentSrc || img.src || '',
            rect: {
              x: Math.max(0, offsetX + rect.left),
              y: Math.max(0, offsetY + rect.top),
              width: rect.width,
              height: rect.height,
            },
          });
        }
        for (const frame of Array.from(doc.querySelectorAll('iframe'))) {
          try {
            const child = frame.contentDocument;
            if (!child) continue;
            const frameRect = frame.getBoundingClientRect();
            scanDoc(child, offsetX + frameRect.left, offsetY + frameRect.top, depth + 1, out);
          } catch (e) {}
        }
      }
      function findRefresh(doc, depth) {
        if (!doc || depth > 4) return null;
        const win = doc.defaultView;
        for (const el of Array.from(doc.querySelectorAll('button,div,span,a,p'))) {
          const text = (el.innerText || el.textContent || '').trim();
          if (!text.includes('点击刷新')) continue;
          if (isVisible(el, win)) return el;
        }
        for (const frame of Array.from(doc.querySelectorAll('iframe'))) {
          try {
            const found = findRefresh(frame.contentDocument, depth + 1);
            if (found) return found;
          } catch (e) {}
        }
        return null;
      }
      const candidates = [];
      scanDoc(document, 0, 0, 0, candidates);
      candidates.sort((a, b) => b.score - a.score);
      const best = candidates[0];
      if (best && typeof best.src === 'string' && best.src.startsWith('data:image/')) {
        return { kind: 'data-url', payload: best.src };
      }
      if (best && best.rect && best.rect.width >= 80 && best.rect.height >= 80) {
        return { kind: 'clip', rect: best.rect };
      }
      const retry = findRefresh(document, 0);
      if (retry) {
        retry.click();
        return { kind: 'retry-needed' };
      }
      return { kind: 'not-found' };
    })()`;
    let value = null;
    for (let attempt = 0; attempt < 4; attempt += 1) {
      const result = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
      value = result?.result?.value || null;
      if (value && value.kind === "retry-needed") {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        continue;
      }
      if (value && (value.kind === "data-url" || value.kind === "clip")) {
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    if (!value) {
      process.exit(2);
    }
    if (value.kind === "clip" && value.rect) {
      const pad = 24;
      const clip = {
        x: Math.max(0, Number(value.rect.x || 0) - pad),
        y: Math.max(0, Number(value.rect.y || 0) - pad),
        width: Math.max(120, Number(value.rect.width || 0) + pad * 2),
        height: Math.max(120, Number(value.rect.height || 0) + pad * 2),
        scale: 1,
      };
      const shot = await send("Page.captureScreenshot", {
        format: "png",
        fromSurface: true,
        clip,
      });
      const data = shot?.data || "";
      if (!data) {
        process.exit(3);
      }
      fs.writeFileSync(outputPath, Buffer.from(data, "base64"));
      process.exit(0);
    }
    if (value.kind !== "data-url" || typeof value.payload !== "string") {
      process.exit(2);
    }
    fs.writeFileSync(outputPath, Buffer.from(value.payload.split(",")[1], "base64"));
    process.exit(0);
  } catch (err) {
    console.error(String(err));
    process.exit(1);
  } finally {
    ws.close();
  }
});
"""
        for tab in page_tabs:
            ws_url = tab.get("webSocketDebuggerUrl") or ""
            if not ws_url:
                continue
            try:
                subprocess.run(
                    ["node", "-e", shipinhao_script, ws_url, output_path],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
            except Exception:
                continue
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
        return None
    node_script = r"""
const fs = require("fs");
const wsUrl = process.argv[1];
const outputPath = process.argv[2];
const platformName = process.argv[3];
const ws = new WebSocket(wsUrl);
let id = 0;
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const msgId = ++id;
    const onMessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.id === msgId) {
        ws.removeEventListener("message", onMessage);
        if (data.error) reject(data.error);
        else resolve(data.result);
      }
    };
    ws.addEventListener("message", onMessage);
    ws.send(JSON.stringify({ id: msgId, method, params }));
  });
}
ws.addEventListener("open", async () => {
  try {
    await send("Runtime.enable");
    const expr = `(() => {
      const selectQr = () => {
        let img = null;
        if (platformName === 'douyin') {
          const text = document.body.innerText || '';
          if (/已失效|二维码失效|二维码已失效/.test(text)) {
            const retry = [...document.querySelectorAll('button,div,span,a,p')].find(el =>
              /刷新|重新获取|重新加载/.test((el.innerText || el.textContent || '').trim())
            );
            if (retry) {
              retry.click();
              return { kind: 'retry-needed' };
            }
          }
          img = document.querySelector('img[class*=qrcode_img]') ||
            Array.from(document.images).find(img => (img.src || '').startsWith('data:image/') && img.naturalWidth >= 180 && img.naturalHeight >= 180);
        } else if (platformName === 'xiaohongshu') {
          const box = document.querySelector('.login-box-container') || document;
          const text = box.innerText || document.body.innerText || '';
          const findByText = (pattern) => [...document.querySelectorAll('button,div,span,a,p')].find(el => {
            const value = (el.innerText || el.textContent || '').trim();
            return value && pattern.test(value);
          });
          if ((/短信登录|验证码登录|手机号登录/.test(text)) && !/APP扫一扫登录|扫码/.test(text)) {
            const qrSwitch = document.querySelector('img.css-wemwzq') || findByText(/APP扫一扫登录|扫码登录|扫码/);
            if (qrSwitch) {
              qrSwitch.click();
              return { kind: 'retry-needed' };
            }
          }
          const candidates = Array.from(box.querySelectorAll('img')).concat(Array.from(document.images));
          img = candidates.find(img => (img.src || '').startsWith('data:image/') && img.naturalWidth >= 160 && img.naturalHeight >= 160) ||
            candidates.find(img => img.naturalWidth >= 160 && img.naturalHeight >= 160 &&
              !(img.naturalWidth === 128 && img.naturalHeight === 128 && /css-wemwzq/.test(img.className || '')));
        } else if (platformName === 'kuaishou') {
          const text = document.body.innerText || '';
          if (text.includes('二维码已失效')) {
            const retry = [...document.querySelectorAll('button,div,span,a,p')].find(el =>
              (el.innerText || el.textContent || '').trim() === '点击刷新'
            );
            if (retry) {
              retry.click();
              return { kind: 'retry-needed' };
            }
          }
          img = document.querySelector('img[alt="qrcode"]') ||
            Array.from(document.images).find(img => (img.src || '').startsWith('data:image/') && img.naturalWidth >= 100 && img.naturalHeight >= 100);
        } else if (platformName === 'shipinhao') {
          const docs = [
            document,
            ...Array.from(document.querySelectorAll('iframe'))
              .map(frame => frame.contentDocument)
              .filter(Boolean),
          ];
          for (const doc of docs) {
            img = doc.querySelector('img.qrcode') ||
              Array.from(doc.images || []).find(img => (img.src || '').startsWith('data:image/') && img.naturalWidth >= 180 && img.naturalHeight >= 180);
            if (img) {
              break;
            }
            const retry = [...doc.querySelectorAll('button,div,span,a,p')].find(el => {
              const text = (el.innerText || el.textContent || '').trim();
              if (!text.includes('点击刷新')) {
                return false;
              }
              const style = el.ownerDocument?.defaultView?.getComputedStyle(el);
              return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
            });
            if (retry) {
              retry.click();
              return { kind: 'retry-needed' };
            }
            const canvas = Array.from(doc.querySelectorAll('canvas')).find(c => c.width >= 180 && c.height >= 180);
            if (canvas) {
              return { kind: 'data-url', payload: canvas.toDataURL('image/png') };
            }
          }
        } else {
          img = Array.from(document.images).find(img => (img.src || '').startsWith('data:image/') && img.naturalWidth >= 180 && img.naturalHeight >= 180);
        }
        if (img && (img.src || '').startsWith('data:image/')) {
          return { kind: 'data-url', payload: img.src };
        }
        const canvas = Array.from(document.querySelectorAll('canvas')).find(c => c.width >= 180 && c.height >= 180);
        if (canvas) {
          return { kind: 'data-url', payload: canvas.toDataURL('image/png') };
        }
        return null;
      };
      if (platformName === 'xiaohongshu') {
        const text = document.querySelector('.login-box-container')?.innerText || document.body.innerText || '';
        if (/二维码已过期|返回重新扫描/.test(text)) {
          const retry = [...document.querySelectorAll('button,div,span,a,p')].find(el =>
            /返回重新扫描|刷新二维码|刷新|重新获取/.test((el.innerText || el.textContent || '').trim())
          );
          if (retry) {
            retry.click();
            return { kind: 'retry-needed' };
          }
        }
      }
      return selectQr();
    })()`;
    let result = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
    let value = result?.result?.value || null;
    if (value && value.kind === "retry-needed") {
      await new Promise((resolve) => setTimeout(resolve, 1800));
      result = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
      value = result?.result?.value || null;
    }
    if (!value || value.kind !== "data-url" || typeof value.payload !== "string") {
      process.exit(2);
    }
    const comma = value.payload.indexOf(",");
    if (comma === -1) {
      process.exit(3);
    }
    const b64 = value.payload.slice(comma + 1);
    fs.writeFileSync(outputPath, Buffer.from(b64, "base64"));
    process.exit(0);
  } catch (err) {
    console.error(String(err));
    process.exit(1);
  } finally {
    ws.close();
  }
});
"""
    for tab in page_tabs:
        ws_url = tab.get("webSocketDebuggerUrl") or ""
        if not ws_url:
            continue
        try:
            subprocess.run(
                ["node", "-e", node_script, ws_url, output_path, platform_name],
                check=True,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except Exception:
            continue
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path
    return output_path if os.path.exists(output_path) and os.path.getsize(output_path) > 0 else None


def _tab_is_logged_in(platform_name: str, tab: dict) -> bool:
    url = (tab.get("url") or "").lower()
    if not url:
        return False
    if url.startswith("chrome-extension://") or url.startswith("devtools://"):
        return False
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
    ready_markers = tuple(m.lower() for m in PLATFORMS[platform_name].get("ready_markers", ()))
    if ready_markers and not any(marker in url for marker in ready_markers):
        return False
    if platform_name == "douyin":
        ws_url = tab.get("webSocketDebuggerUrl") or ""
        if ws_url:
            try:
                node_script = r"""
const wsUrl = process.argv[1];
const ws = new WebSocket(wsUrl);
let id = 0;
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const msgId = ++id;
    const onMessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.id === msgId) {
        ws.removeEventListener("message", onMessage);
        if (data.error) reject(data.error);
        else resolve(data.result);
      }
    };
    ws.addEventListener("message", onMessage);
    ws.send(JSON.stringify({ id: msgId, method, params }));
  });
}
ws.addEventListener("open", async () => {
  try {
    await send("Runtime.enable");
    for (let i = 0; i < 3; i += 1) {
      const result = await send("Runtime.evaluate", {
        expression: `(() => {
          const text = (document.body && document.body.innerText || '').slice(0, 12000);
          const title = document.title || '';
          const url = location.href || '';
          const buttons = Array.from(document.querySelectorAll('button, [role="button"], a, span, div'))
            .map(el => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim())
            .filter(Boolean)
            .slice(0, 80);
          const hasUploadInput = !!document.querySelector(
            'div[class^="container"] input[type="file"], div.progress-div input[type="file"], input[type="file"]'
          );
          const loginSignals = text + '\\n' + title;
          const hasLoginText = /扫码登录|手机号登录|验证码登录|密码登录|登录抖音创作者中心|登录\\/注册|获取验证码|打开「抖音APP」|我是创作者|我是MCN机构/.test(loginSignals);
          const hasLoginForm = !!document.querySelector(
            'input[type="tel"], input[placeholder*="手机号"], input[placeholder*="验证码"]'
          );
          const hasReadyUi = hasUploadInput ||
            /上传视频|发布视频|发布作品|重新上传|作品描述|添加简介|定时发布|封面设置|声明内容由AI生成/.test(text) ||
            buttons.some(v => /上传视频|发布视频|发布作品|选择视频|重新上传|定时发布|作品描述|封面设置|发布/.test(v));
          return {
            url,
            title,
            hasUploadInput,
            hasLoginText: hasLoginText || hasLoginForm,
            hasReadyText: hasReadyUi &&
              /creator\\.douyin\\.com\\/creator-micro\\/content\\/upload/.test(url) &&
              !(hasLoginText || hasLoginForm)
          };
        })()`,
        returnByValue: true
      });
      const payload = result.result.value || {};
      if (payload.hasReadyText && !payload.hasLoginText) {
        console.log(JSON.stringify(payload));
        ws.close();
        return;
      }
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    const result = await send("Runtime.evaluate", {
      expression: `(() => {
        const text = (document.body && document.body.innerText || '').slice(0, 12000);
        const title = document.title || '';
        const url = location.href || '';
        const buttons = Array.from(document.querySelectorAll('button, [role="button"], a, span, div'))
          .map(el => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim())
          .filter(Boolean)
          .slice(0, 80);
        const hasUploadInput = !!document.querySelector(
          'div[class^="container"] input[type="file"], div.progress-div input[type="file"], input[type="file"]'
        );
        const loginSignals = text + '\\n' + title;
        const hasLoginText = /扫码登录|手机号登录|验证码登录|密码登录|登录抖音创作者中心|登录\\/注册|获取验证码|打开「抖音APP」|我是创作者|我是MCN机构/.test(loginSignals);
        const hasLoginForm = !!document.querySelector(
          'input[type="tel"], input[placeholder*="手机号"], input[placeholder*="验证码"]'
        );
        const hasReadyUi = hasUploadInput ||
          /上传视频|发布视频|发布作品|重新上传|作品描述|添加简介|定时发布|封面设置|声明内容由AI生成/.test(text) ||
          buttons.some(v => /上传视频|发布视频|发布作品|选择视频|重新上传|定时发布|作品描述|封面设置|发布/.test(v));
        return {
          url,
          title,
          hasUploadInput,
          hasLoginText: hasLoginText || hasLoginForm,
          hasReadyText: hasReadyUi &&
            /creator\\.douyin\\.com\\/creator-micro\\/content\\/upload/.test(url) &&
            !(hasLoginText || hasLoginForm)
        };
      })()`,
      returnByValue: true
    });
    console.log(JSON.stringify(result.result.value || {}));
  } catch (e) {
    console.log(JSON.stringify({ error: String(e) }));
  }
  ws.close();
});
"""
                last_payload = {}
                for _ in range(3):
                    result = subprocess.run(
                        ["node", "-e", node_script, ws_url],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    payload = json.loads((result.stdout or "").strip() or "{}")
                    last_payload = payload
                    if payload.get("hasReadyText") and not payload.get("hasLoginText") and _has_required_login_cookies(platform_name, tab):
                        return True
                    time.sleep(0.3)
                if last_payload.get("error"):
                    return False
                if last_payload.get("hasLoginText"):
                    return False
                if not last_payload.get("hasReadyText"):
                    return False
                if not _has_required_login_cookies(platform_name, tab):
                    return False
            except Exception:
                return False
    if platform_name == "xiaohongshu":
        ws_url = tab.get("webSocketDebuggerUrl") or ""
        if ws_url:
            try:
                node_script = r"""
const wsUrl = process.argv[1];
const ws = new WebSocket(wsUrl);
let id = 0;
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const msgId = ++id;
    const onMessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.id === msgId) {
        ws.removeEventListener("message", onMessage);
        if (data.error) reject(data.error);
        else resolve(data.result);
      }
    };
    ws.addEventListener("message", onMessage);
    ws.send(JSON.stringify({ id: msgId, method, params }));
  });
}
ws.addEventListener("open", async () => {
  try {
    await send("Runtime.enable");
    for (let i = 0; i < 3; i += 1) {
      const result = await send("Runtime.evaluate", {
        expression: `(() => {
          const text = (document.body && document.body.innerText || '').slice(0, 12000);
          const title = document.title || '';
          const url = location.href || '';
          const buttons = Array.from(document.querySelectorAll('button, [role="button"], a, span, div'))
            .map(el => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim())
            .filter(Boolean)
            .slice(0, 120);
          const hasUploadInput = !!document.querySelector(
            'input[type="file"], input[accept*="video"], input[accept*="image"], [class*="upload"] input[type="file"]'
          );
          const loginSignals = text + '\\n' + title;
          const hasLoginText = /短信登录|验证码登录|扫码登录|APP扫一扫登录|手机号登录|登录小红书创作服务平台|登录小红书|立即登录|同意并登录/.test(loginSignals);
          const hasLoginForm = !!document.querySelector(
            'input[type="tel"], input[type="password"], input[placeholder*="手机号"], input[placeholder*="验证码"], input[placeholder*="密码"]'
          );
          const hasReadyUi = hasUploadInput ||
            /发布笔记|发布视频|上传视频|上传图文|写长文|创作服务平台|专业号中心|内容管理|数据中心|笔记管理|拖拽视频到此或点击上传|草稿箱/.test(text) ||
            buttons.some(v => /发布笔记|发布视频|上传视频|上传图文|写长文|选择视频|点击上传|内容管理|草稿箱/.test(v));
          return {
            url,
            title,
            hasUploadInput,
            hasLoginText: hasLoginText || hasLoginForm,
            hasReadyText: hasReadyUi &&
              /creator\\.xiaohongshu\\.com\\/(publish\\/publish|publish\\/notemanager|content\\/upload|creator\\/home)/.test(url) &&
              !(hasLoginText || hasLoginForm)
          };
        })()`,
        returnByValue: true
      });
      const payload = result.result.value || {};
      if (payload.hasReadyText && !payload.hasLoginText) {
        console.log(JSON.stringify(payload));
        ws.close();
        return;
      }
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    const result = await send("Runtime.evaluate", {
      expression: `(() => {
        const text = (document.body && document.body.innerText || '').slice(0, 12000);
        const title = document.title || '';
        const url = location.href || '';
        const buttons = Array.from(document.querySelectorAll('button, [role="button"], a, span, div'))
          .map(el => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim())
          .filter(Boolean)
          .slice(0, 120);
        const hasUploadInput = !!document.querySelector(
          'input[type="file"], input[accept*="video"], input[accept*="image"], [class*="upload"] input[type="file"]'
        );
        const loginSignals = text + '\\n' + title;
        const hasLoginText = /短信登录|验证码登录|扫码登录|APP扫一扫登录|手机号登录|登录小红书创作服务平台|登录小红书|立即登录|同意并登录/.test(loginSignals);
        const hasLoginForm = !!document.querySelector(
          'input[type="tel"], input[type="password"], input[placeholder*="手机号"], input[placeholder*="验证码"], input[placeholder*="密码"]'
        );
        const hasReadyUi = hasUploadInput ||
          /发布笔记|发布视频|上传视频|上传图文|写长文|创作服务平台|专业号中心|内容管理|数据中心|笔记管理|拖拽视频到此或点击上传|草稿箱/.test(text) ||
          buttons.some(v => /发布笔记|发布视频|上传视频|上传图文|写长文|选择视频|点击上传|内容管理|草稿箱/.test(v));
        return {
          url,
          title,
          hasUploadInput,
          hasLoginText: hasLoginText || hasLoginForm,
          hasReadyText: hasReadyUi &&
            /creator\\.xiaohongshu\\.com\\/(publish\\/publish|publish\\/notemanager|content\\/upload|creator\\/home)/.test(url) &&
            !(hasLoginText || hasLoginForm)
        };
      })()`,
      returnByValue: true
    });
    console.log(JSON.stringify(result.result.value || {}));
  } catch (e) {
    console.log(JSON.stringify({ error: String(e) }));
  }
  ws.close();
});
"""
                last_payload = {}
                for _ in range(3):
                    result = subprocess.run(
                        ["node", "-e", node_script, ws_url],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    payload = json.loads((result.stdout or "").strip() or "{}")
                    last_payload = payload
                    if payload.get("hasReadyText") and not payload.get("hasLoginText") and _has_required_login_cookies(platform_name, tab):
                        return True
                    time.sleep(0.3)
                if last_payload.get("error"):
                    return False
                if last_payload.get("hasLoginText"):
                    return False
                if not last_payload.get("hasReadyText"):
                    return False
                if not _has_required_login_cookies(platform_name, tab):
                    return False
            except Exception:
                return False
    if platform_name == "kuaishou":
        ws_url = tab.get("webSocketDebuggerUrl") or ""
        if ws_url:
            try:
                expression = r"""(() => {
                  const text = (document.body && document.body.innerText || '').slice(0, 12000);
                  const title = document.title || '';
                  const url = location.href || '';
                  const buttons = Array.from(document.querySelectorAll('button, [role="button"], a, span, div'))
                    .map(el => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim())
                    .filter(Boolean)
                    .slice(0, 120);
                  const hasUploadInput = !!document.querySelector(
                    'input[type="file"], input[accept*="video"], input[accept*="mp4"], [class*="upload"] input[type="file"]'
                  );
                  const loginSignals = text + '\n' + title;
                  const hasLoginText = /扫码登录|验证码登录|短信登录|登录快手创作者服务平台|手机号登录|账号登录|请完成验证后继续访问|同意并登录|快手APP扫码/.test(loginSignals);
                  const hasReadyUi = hasUploadInput ||
                    /发布作品|发布视频|上传视频|上传图文|上传全景视频|拖拽视频到此或点击上传|作品描述|封面设置|定时发布/.test(text) ||
                    buttons.some(v => /发布作品|发布视频|上传视频|选择视频|点击上传|发布/.test(v));
                  return {
                    url,
                    title,
                    hasUploadInput,
                    hasLoginText,
                    hasReadyText: hasReadyUi &&
                      /cp\.kuaishou\.com\/article\/publish/.test(url) &&
                      !/passport\.kuaishou\.com/.test(url) &&
                      !hasLoginText
                  };
                })()"""
                last_payload = {}
                for _ in range(3):
                    payload = asyncio.run(_cdp_runtime_evaluate(ws_url, expression, timeout=8.0)) or {}
                    last_payload = payload
                    if payload.get("hasReadyText") and not payload.get("hasLoginText") and _has_required_login_cookies(platform_name, tab):
                        return True
                    time.sleep(0.3)
                if last_payload.get("error"):
                    return False
                if last_payload.get("hasLoginText"):
                    return False
                if not last_payload.get("hasReadyText"):
                    return False
                if not _has_required_login_cookies(platform_name, tab):
                    return False
            except Exception:
                return False
    if platform_name == "shipinhao":
        ws_url = tab.get("webSocketDebuggerUrl") or ""
        if ws_url:
            try:
                node_script = r"""
const wsUrl = process.argv[1];
const ws = new WebSocket(wsUrl);
let id = 0;
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const msgId = ++id;
    const onMessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.id === msgId) {
        ws.removeEventListener("message", onMessage);
        if (data.error) reject(data.error);
        else resolve(data.result);
      }
    };
    ws.addEventListener("message", onMessage);
    ws.send(JSON.stringify({ id: msgId, method, params }));
  });
}
ws.addEventListener("open", async () => {
  try {
    await send("Runtime.enable");
    for (let i = 0; i < 3; i += 1) {
      const result = await send("Runtime.evaluate", {
        expression: `(() => {
          const text = (document.body && document.body.innerText || '').slice(0, 12000);
          const title = document.title || '';
          const url = location.href || '';
          const buttons = Array.from(document.querySelectorAll('button, [role="button"], a, span, div'))
            .map(el => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim())
            .filter(Boolean)
            .slice(0, 120);
          const hasUploadInput = !!document.querySelector(
            'input[type="file"], input[accept*="video"], [class*="upload"] input[type="file"]'
          );
          const loginSignals = text + '\\n' + title;
          const hasLoginText = /微信扫码|扫码登录|请使用微信扫码|登录后继续|登录后可继续|请先登录/.test(loginSignals);
          const hasReadyUi = hasUploadInput ||
            /发表视频|上传视频|拖拽|选择视频|视频描述|扩展链接|首页|内容管理|草稿箱|数据中心|视频号 · 助手/.test(text) ||
            buttons.some(v => /发表视频|上传视频|选择视频|内容管理|草稿箱|数据中心/.test(v));
          return {
            url,
            title,
            hasUploadInput,
            hasLoginText,
            hasReadyText: hasReadyUi &&
              /channels\\.weixin\\.qq\\.com\\/platform\\/post\\/create/.test(url) &&
              !hasLoginText
          };
        })()`,
        returnByValue: true
      });
      const payload = result.result.value || {};
      if (payload.hasReadyText && !payload.hasLoginText) {
        console.log(JSON.stringify(payload));
        ws.close();
        return;
      }
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    const result = await send("Runtime.evaluate", {
      expression: `(() => {
        const text = (document.body && document.body.innerText || '').slice(0, 12000);
        const title = document.title || '';
        const url = location.href || '';
        const buttons = Array.from(document.querySelectorAll('button, [role="button"], a, span, div'))
          .map(el => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim())
          .filter(Boolean)
          .slice(0, 120);
        const hasUploadInput = !!document.querySelector(
          'input[type="file"], input[accept*="video"], [class*="upload"] input[type="file"]'
        );
        const loginSignals = text + '\\n' + title;
        const hasLoginText = /微信扫码|扫码登录|请使用微信扫码|登录后继续|登录后可继续|请先登录/.test(loginSignals);
        const hasReadyUi = hasUploadInput ||
          /发表视频|上传视频|拖拽|选择视频|视频描述|扩展链接|首页|内容管理|草稿箱|数据中心|视频号 · 助手/.test(text) ||
          buttons.some(v => /发表视频|上传视频|选择视频|内容管理|草稿箱|数据中心/.test(v));
        return {
          url,
          title,
          hasUploadInput,
          hasLoginText,
          hasReadyText: hasReadyUi &&
            /channels\\.weixin\\.qq\\.com\\/platform\\/post\\/create/.test(url) &&
            !hasLoginText
        };
      })()`,
      returnByValue: true
    });
    console.log(JSON.stringify(result.result.value || {}));
  } catch (e) {
    console.log(JSON.stringify({ error: String(e) }));
  }
  ws.close();
});
"""
                last_payload = {}
                for _ in range(3):
                    result = subprocess.run(
                        ["node", "-e", node_script, ws_url],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    payload = json.loads((result.stdout or "").strip() or "{}")
                    last_payload = payload
                    if payload.get("hasReadyText") and not payload.get("hasLoginText") and _has_required_login_cookies(platform_name, tab):
                        return True
                    time.sleep(0.3)
                if last_payload.get("error"):
                    return False
                if last_payload.get("hasLoginText"):
                    return False
                if not last_payload.get("hasReadyText"):
                    return False
                if not _has_required_login_cookies(platform_name, tab):
                    return False
            except Exception:
                return False
    markers = tuple(m.lower() for m in PLATFORMS[platform_name]["login_markers"])
    return not any(marker in url for marker in markers)


def capture_login_screenshot(platform_name: str, root: Path | None = None) -> str | None:
    root = root or project_root()
    screenshot_dir = root / "logs" / "auth_qr"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    output_path = screenshot_dir / f"{platform_name}_login_qr.png"
    try:
        output_path.unlink(missing_ok=True)
    except Exception:
        pass
    direct_qr_path = _extract_qr_image_via_cdp(platform_name, str(output_path))
    if direct_qr_path:
        return direct_qr_path
    return None


def _revive_connect_session_for_check(
    platform_name: str,
    root: Path,
    timeout: float = 12.0,
) -> list[dict]:
    cfg = PLATFORMS[platform_name]
    profile_dir = profile_dir_for(platform_name, root)
    if not profile_dir.exists():
        return []
    try:
        launch_connect_chrome(platform_name, root)
    except Exception:
        return []
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_port_listening(cfg["port"]):
            tabs = ensure_page_target(platform_name, retries=1, wait_seconds=0.5)
            if tabs:
                return tabs
        time.sleep(0.25)
    return []


def _post_revival_stabilize(platform_name: str) -> None:
    if platform_name != "shipinhao":
        return
    time.sleep(2.0)


def auto_recover_session(
    platform_name: str,
    root: Path | None = None,
    timeout: float = 15.0,
) -> tuple[bool, str]:
    """
    自动恢复平台会话
    当 check_platform_login 返回 False 时调用此函数尝试恢复
    流程：启动 Chrome → 打开目标页 → 等待就绪
    返回：(是否成功，消息)
    """
    root = root or project_root()
    cfg = PLATFORMS[platform_name]
    label = cfg["label"]
    
    # 检查 profile 目录是否存在
    profile_dir = profile_dir_for(platform_name, root)
    if not profile_dir.exists():
        return False, f"{label} 还没有登录目录，需要先扫码登录"
    
    # 检查端口是否监听
    if is_port_listening(cfg["port"]):
        # 端口已监听，只需打开目标页面
        tabs = ensure_page_target(platform_name, retries=2, wait_seconds=0.8)
        if tabs:
            for tab in tabs:
                if _tab_is_logged_in(platform_name, tab):
                    return True, f"{label} 已登录，可复用：{tab.get('url', '')}"
        # 打开目标页面
        open_target_tab(platform_name)
        time.sleep(2)
        tabs = ensure_page_target(platform_name, retries=2, wait_seconds=0.8)
        if tabs:
            for tab in tabs:
                if _tab_is_logged_in(platform_name, tab):
                    return True, f"{label} 已登录，可复用：{tab.get('url', '')}"
        return False, f"{label} 端口已监听但未找到已登录页面"
    
    # 端口未监听，需要启动 Chrome
    print(f"   🔄 {label} 端口 {cfg['port']} 未监听，正在启动 Chrome...")
    try:
        launch_connect_chrome(platform_name, root)
    except Exception as e:
        return False, f"{label} 启动 Chrome 失败：{e}"
    
    # 等待端口监听
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_port_listening(cfg["port"]):
            break
        time.sleep(0.3)
    else:
        return False, f"{label} 启动 Chrome 后端口仍未监听"
    
    # 打开目标页面
    print(f"   📑 打开 {label} 目标页面...")
    open_target_tab(platform_name)
    time.sleep(3)
    
    # 检查页面是否就绪
    tabs = ensure_page_target(platform_name, retries=3, wait_seconds=1.0)
    if not tabs:
        return False, f"{label} 无法打开目标页面"
    
    # 检查是否已登录
    for tab in tabs:
        if _tab_is_logged_in(platform_name, tab):
            return True, f"{label} 已登录，可复用：{tab.get('url', '')}"
    
    # 页面已打开但可能还在加载，等待一下再检查
    time.sleep(2)
    tabs = ensure_page_target(platform_name, retries=2, wait_seconds=0.8)
    for tab in tabs:
        if _tab_is_logged_in(platform_name, tab):
            return True, f"{label} 已登录，可复用：{tab.get('url', '')}"
    
    return False, f"{label} 页面已打开但检测到未登录状态"


def check_platform_login(
    platform_name: str,
    root: Path | None = None,
    passive: bool = False,
) -> tuple[bool, str]:
    root = root or project_root()
    cfg = PLATFORMS[platform_name]
    profile_dir = profile_dir_for(platform_name, root)
    revived = False
    if not is_port_listening(cfg["port"]):
        if not profile_dir.exists():
            return False, f"{cfg['label']} 还没有登录目录: {profile_dir}"
        # profile 目录存在，说明之前登录过，尝试启动 Chrome 检查 cookies
        # 注意：即使 passive=True 也会启动，因为"浏览器没开"≠"登录失效"
        tabs = _revive_connect_session_for_check(platform_name, root)
        if not tabs:
            return False, f"{cfg['label']} connect 端口 {cfg['port']} 未监听，且无法恢复本地会话"
        _post_revival_stabilize(platform_name)
        tabs = ensure_page_target(platform_name, retries=2, wait_seconds=0.8)
        revived = True
    else:
        tabs = devtools_tabs(cfg["port"]) if passive else ensure_page_target(platform_name)
    if not tabs:
        if passive:
            return False, f"{cfg['label']} connect Chrome 当前没有可复用标签页"
        return False, f"{cfg['label']} connect Chrome 没有可复用标签页"
    for tab in tabs:
        if _tab_is_logged_in(platform_name, tab):
            if not profile_dir.exists():
                return True, f"{cfg['label']} 已登录，可复用外部 connect 会话: {tab.get('url', '')}"
            suffix = "（已自动恢复本地会话）" if revived else ""
            return True, f"{cfg['label']} 已登录，可复用{suffix}: {tab.get('url', '')}"
    if passive:
        cookie_tab = _find_reusable_session_by_cookies(platform_name, tabs)
        if cookie_tab:
            cookie_url = cookie_tab.get("url") or ""
            return True, f"{cfg['label']} 已检测到本地可复用会话 cookie: {cookie_url}"
        return False, f"{cfg['label']} 当前未发现可直接复用的已登录页面"
    open_target_tab(platform_name)
    time.sleep(1)
    for tab in ensure_page_target(platform_name, retries=1):
        if _tab_is_logged_in(platform_name, tab):
            return True, f"{cfg['label']} 已登录，可复用: {tab.get('url', '')}"
    return False, f"{cfg['label']} 当前仍停在登录页"


def force_platform_login(
    platform_name: str,
    timeout: int = 300,
    notify_wechat: bool = False,
) -> tuple[bool, str]:
    """强制重新登录，跳过检查直接打开登录页获取二维码"""
    root = project_root()
    cfg = PLATFORMS[platform_name]
    
    # 确保浏览器已启动
    if not is_port_listening(cfg["port"]):
        launch_connect_chrome(platform_name, root)
        deadline = time.time() + 20
        while time.time() < deadline:
            if is_port_listening(cfg["port"]):
                break
            time.sleep(0.25)
    
    # 打开登录页（强制打开，不复用现有标签页）
    open_target_tab(platform_name, force_new=True)
    
    # 获取二维码截图
    time.sleep(2)  # 等待页面加载
    screenshot_path = capture_login_screenshot(platform_name, root)
    if screenshot_path:
        print(f"{cfg['label']} 登录二维码已保存：{screenshot_path}")
        if notify_wechat:
            if send_wechat_notification(platform_name, screenshot_path):
                print(f"{cfg['label']} 登录二维码已发送到微信")
            else:
                print(f"{cfg['label']} 登录二维码发送到微信失败")
    else:
        print(f"{cfg['label']} 登录页已打开，但本次未提取到二维码图片")
    
    last_qr_refresh = time.time()

    deadline = time.time() + timeout
    while time.time() < deadline:
        ok, msg = check_platform_login(platform_name, root)
        if ok:
            return True, msg
        if time.time() - last_qr_refresh >= 120:
            screenshot_path = capture_login_screenshot(platform_name, root)
            if screenshot_path:
                print(f"{cfg['label']} 登录二维码已刷新：{screenshot_path}")
            last_qr_refresh = time.time()
        time.sleep(3)
    return False, f"{cfg['label']} 登录超时，请稍后重试"


def ensure_platform_login(
    platform_name: str,
    timeout: int = 300,
    notify_wechat: bool = False,
) -> tuple[bool, str]:
    root = project_root()
    cfg = PLATFORMS[platform_name]
    ok, msg = check_platform_login(platform_name, root)
    if ok:
        return True, msg

    if not is_port_listening(cfg["port"]):
        launch_connect_chrome(platform_name, root)
        deadline = time.time() + 20
        while time.time() < deadline:
            if is_port_listening(cfg["port"]):
                break
            time.sleep(0.25)
    open_target_tab(platform_name)
    screenshot_path = capture_login_screenshot(platform_name, root)
    if screenshot_path:
        print(f"{cfg['label']} 登录二维码已保存：{screenshot_path}")
        if notify_wechat:
            if send_wechat_notification(platform_name, screenshot_path):
                print(f"{cfg['label']} 登录二维码已发送到微信")
            else:
                print(f"{cfg['label']} 登录二维码发送到微信失败")
    else:
        print(f"{cfg['label']} 登录页已打开，但本次未提取到二维码图片")
    last_qr_refresh = time.time()

    deadline = time.time() + timeout
    while time.time() < deadline:
        ok, msg = check_platform_login(platform_name, root)
        if ok:
            return True, msg
        if time.time() - last_qr_refresh >= 120:
            screenshot_path = capture_login_screenshot(platform_name, root)
            if screenshot_path:
                print(f"{cfg['label']} 登录二维码已刷新：{screenshot_path}")
            last_qr_refresh = time.time()
        time.sleep(3)
    return False, f"{cfg['label']} 登录超时，请稍后重试"


def _main() -> int:
    parser = argparse.ArgumentParser(description="四平台 connect 登录助手（auth skill 版，单次只处理一个平台）")
    parser.add_argument("--platform", required=True, choices=CLI_PLATFORMS, help="目标平台；当前入口只保留视频号")
    parser.add_argument("--check-only", action="store_true", help="仅检查当前登录是否可复用")
    parser.add_argument("--close-after-check", action="store_true", help="仅检查时在返回结果后关闭当前平台 connect Chrome")
    parser.add_argument("--notify-wechat", action="store_true", help="登录页打开后把二维码发送到微信")
    parser.add_argument("--force-login", action="store_true", help="强制重新登录，跳过检查直接打开登录页")
    parser.add_argument("--timeout", type=int, default=300, help="等待登录超时时间（秒）")
    parser.add_argument("--project-root", default="", help="项目根目录；不传则默认取当前仓库")
    args = parser.parse_args()

    global _PROJECT_ROOT_OVERRIDE
    if args.project_root:
        _PROJECT_ROOT_OVERRIDE = Path(args.project_root).expanduser().resolve()

    if args.check_only:
        ok, msg = check_platform_login(args.platform)
        # 检测完自动关闭浏览器
        closed = close_connect_browser(args.platform)
        msg = f"{msg}\n{PLATFORMS[args.platform]['label']} connect Chrome 已关闭" if closed else f"{msg}\n{PLATFORMS[args.platform]['label']} connect Chrome 未关闭（可能本来就未启动）"
    elif args.force_login:
        # 强制重新登录，跳过检查
        ok, msg = force_platform_login(
            args.platform,
            timeout=args.timeout,
            notify_wechat=args.notify_wechat,
        )
    else:
        ok, msg = ensure_platform_login(
            args.platform,
            timeout=args.timeout,
            notify_wechat=args.notify_wechat,
        )

    print(msg)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(_main())
