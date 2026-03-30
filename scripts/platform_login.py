#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-platform connect-login helper for the four upload platforms.

This copy lives inside the auth skill so it can be reused independently.
"""
from __future__ import annotations

import argparse
import json
import os
import platform as sys_platform
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
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
    },
    "shipinhao": {
        "label": "视频号",
        "port": 9226,
        "profile_dir": "chrome_connect_sph",
        "url": "https://channels.weixin.qq.com/platform/post/create",
        "ready_markers": ("channels.weixin.qq.com/platform/post/create",),
        "login_markers": ("login", "mp.weixin.qq.com", "微信扫码", "扫码登录"),
        "qr_switch_texts": (),
    },
}

_PROJECT_ROOT_OVERRIDE: Path | None = None


def project_root() -> Path:
    return _PROJECT_ROOT_OVERRIDE or Path(__file__).resolve().parents[1]


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


def _devtools_get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "platform-login-helper"})
    with urllib.request.urlopen(req, timeout=2) as resp:
        return json.loads(resp.read().decode("utf-8"))


def devtools_tabs(port: int) -> list[dict]:
    try:
        return _devtools_get(f"http://127.0.0.1:{port}/json/list")
    except Exception:
        return []


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


def open_target_tab(platform_name: str) -> bool:
    port = PLATFORMS[platform_name]["port"]
    tabs = devtools_tabs(port)
    if any(tab.get("type") == "page" for tab in tabs):
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
    const expr = `(() => {
      const text = document.body.innerText || '';
      if (!location.href.includes('passport.kuaishou.com')) {
        const loginEntry = [...document.querySelectorAll('a,button,div,span,p')].find(el =>
          (el.innerText || el.textContent || '').trim() === '立即登录'
        );
        if (loginEntry) {
          loginEntry.click();
          return { kind: 'retry-needed', waitMs: 1800 };
        }
      }
      if (text.includes('扫码登录') && !text.includes('快手APP，扫码登录')) {
        const scanEntry = [...document.querySelectorAll('a,button,div,span,p')].find(el =>
          (el.innerText || el.textContent || '').trim() === '扫码登录'
        );
        if (scanEntry) {
          scanEntry.click();
          return { kind: 'retry-needed', waitMs: 1500 };
        }
      }
      if (text.includes('二维码已失效')) {
        const retry = [...document.querySelectorAll('button,div,span,a,p')].find(el =>
          (el.innerText || el.textContent || '').trim() === '点击刷新'
        );
        if (retry) {
          retry.click();
          return { kind: 'retry-needed', waitMs: 1200 };
        }
      }
      const img = document.querySelector('img[alt="qrcode"]') ||
        Array.from(document.images).find(img =>
          (img.src || '').startsWith('data:image/') && img.naturalWidth >= 100 && img.naturalHeight >= 100
        );
      if (img && (img.src || '').startsWith('data:image/')) {
        return { kind: 'data-url', payload: img.src };
      }
      return null;
    })()`;
    let attempts = 0;
    while (attempts < 5) {
      let result = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
      let value = result?.result?.value || null;
      if (value && value.kind === "data-url" && typeof value.payload === "string") {
        fs.writeFileSync(outputPath, Buffer.from(value.payload.split(",")[1], "base64"));
        process.exit(0);
      }
      if (value && value.kind === "retry-needed") {
        await new Promise((resolve) => setTimeout(resolve, value.waitMs || 1500));
        attempts += 1;
        continue;
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
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
          const text = (document.body && document.body.innerText || '').slice(0, 4000);
          return {
            text,
            hasLoginText: /扫码登录|手机号登录|验证码登录|登录抖音创作者中心/.test(text),
            hasReadyText: /创作者服务中心|创作者中心|发布作品|上传视频|发布视频|作品管理|新的创作|数据中心/.test(text)
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
        const text = (document.body && document.body.innerText || '').slice(0, 4000);
        return {
          text,
          hasLoginText: /扫码登录|手机号登录|验证码登录|登录抖音创作者中心/.test(text),
          hasReadyText: /创作者服务中心|创作者中心|发布作品|上传视频|发布视频|作品管理|新的创作|数据中心/.test(text)
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
                    if payload.get("hasReadyText") and not payload.get("hasLoginText"):
                        return True
                    time.sleep(0.3)
                if last_payload.get("error"):
                    return False
                if last_payload.get("hasLoginText"):
                    return False
                if not last_payload.get("hasReadyText"):
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
          const text = (document.body && document.body.innerText || '').slice(0, 4000);
          return {
            text,
            hasLoginText: /短信登录|验证码登录|扫码登录|APP扫一扫登录|手机号登录|登录小红书创作服务平台/.test(text),
            hasReadyText: /发布笔记|发布视频|上传视频|创作服务平台|专业号中心|内容管理|数据中心|笔记管理/.test(text)
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
        const text = (document.body && document.body.innerText || '').slice(0, 4000);
        return {
          text,
          hasLoginText: /短信登录|验证码登录|扫码登录|APP扫一扫登录|手机号登录|登录小红书创作服务平台/.test(text),
          hasReadyText: /发布笔记|发布视频|上传视频|创作服务平台|专业号中心|内容管理|数据中心|笔记管理/.test(text)
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
                    if payload.get("hasReadyText") and not payload.get("hasLoginText"):
                        return True
                    time.sleep(0.3)
                if last_payload.get("error"):
                    return False
                if last_payload.get("hasLoginText"):
                    return False
                if not last_payload.get("hasReadyText"):
                    return False
            except Exception:
                return False
    if platform_name == "kuaishou":
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
          const text = (document.body && document.body.innerText || '').slice(0, 4000);
          return {
            text,
            hasLoginText: /扫码登录|验证码登录|短信登录|登录快手创作者服务平台|手机号登录/.test(text),
            hasReadyText: /发布作品|发布视频|上传视频|上传图文|上传全景视频|拖拽视频到此或点击上传|作品描述|封面设置|定时发布|快手创作者服务平台|作品管理|内容管理|数据中心/.test(text)
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
        const text = (document.body && document.body.innerText || '').slice(0, 4000);
        return {
          text,
          hasLoginText: /扫码登录|验证码登录|短信登录|登录快手创作者服务平台|手机号登录/.test(text),
          hasReadyText: /发布作品|发布视频|上传视频|上传图文|上传全景视频|拖拽视频到此或点击上传|作品描述|封面设置|定时发布|快手创作者服务平台|作品管理|内容管理|数据中心/.test(text)
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
                    if payload.get("hasReadyText") and not payload.get("hasLoginText"):
                        return True
                    time.sleep(0.3)
                if last_payload.get("error"):
                    return False
                if last_payload.get("hasLoginText"):
                    return False
                if not last_payload.get("hasReadyText"):
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
          const text = (document.body && document.body.innerText || '').slice(0, 4000);
          return {
            text,
            hasLoginText: /微信扫码|扫码登录|请使用微信扫码/.test(text),
            hasReadyText: /发表视频|上传视频|拖拽|选择视频|视频描述|扩展链接|首页|内容管理|草稿箱|数据中心|视频号 · 助手/.test(text)
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
        const text = (document.body && document.body.innerText || '').slice(0, 4000);
        return {
          text,
          hasLoginText: /微信扫码|扫码登录|请使用微信扫码/.test(text),
          hasReadyText: /发表视频|上传视频|拖拽|选择视频|视频描述|扩展链接|首页|内容管理|草稿箱|数据中心|视频号 · 助手/.test(text)
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
                    if payload.get("hasReadyText") and not payload.get("hasLoginText"):
                        return True
                    time.sleep(0.3)
                if last_payload.get("error"):
                    return False
                if last_payload.get("hasLoginText"):
                    return False
                if not last_payload.get("hasReadyText"):
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


def check_platform_login(platform_name: str, root: Path | None = None) -> tuple[bool, str]:
    root = root or project_root()
    cfg = PLATFORMS[platform_name]
    profile_dir = profile_dir_for(platform_name, root)
    revived = False
    if not is_port_listening(cfg["port"]):
        if not profile_dir.exists():
            return False, f"{cfg['label']} 还没有登录目录: {profile_dir}"
        tabs = _revive_connect_session_for_check(platform_name, root)
        if not tabs:
            return False, f"{cfg['label']} connect 端口 {cfg['port']} 未监听，且无法恢复本地会话"
        revived = True
    else:
        tabs = ensure_page_target(platform_name)
    if not tabs:
        return False, f"{cfg['label']} connect Chrome 没有可复用标签页"
    for tab in tabs:
        if _tab_is_logged_in(platform_name, tab):
            if not profile_dir.exists():
                return True, f"{cfg['label']} 已登录，可复用外部 connect 会话: {tab.get('url', '')}"
            suffix = "（已自动恢复本地会话）" if revived else ""
            return True, f"{cfg['label']} 已登录，可复用{suffix}: {tab.get('url', '')}"
    open_target_tab(platform_name)
    time.sleep(1)
    for tab in ensure_page_target(platform_name, retries=1):
        if _tab_is_logged_in(platform_name, tab):
            return True, f"{cfg['label']} 已登录，可复用: {tab.get('url', '')}"
    return False, f"{cfg['label']} 当前仍停在登录页"


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
    else:
        print(f"{cfg['label']} 登录页已打开，但本次未提取到二维码图片")
    last_qr_refresh = time.time()

    if notify_wechat:
        if screenshot_path and send_wechat_notification(platform_name, screenshot_path):
            print(f"{cfg['label']} 登录二维码已发送到微信：{screenshot_path}")
        else:
            print(f"{cfg['label']} 登录页已打开，但二维码发送到微信失败")

    deadline = time.time() + timeout
    while time.time() < deadline:
        ok, msg = check_platform_login(platform_name, root)
        if ok:
            return True, msg
        if time.time() - last_qr_refresh >= 120:
            screenshot_path = capture_login_screenshot(platform_name, root)
            if screenshot_path:
                print(f"{cfg['label']} 登录二维码已刷新：{screenshot_path}")
                if notify_wechat:
                    send_wechat_notification(platform_name, screenshot_path)
            last_qr_refresh = time.time()
        time.sleep(3)
    return False, f"{cfg['label']} 登录超时，请稍后重试"


def _main() -> int:
    parser = argparse.ArgumentParser(description="四平台 connect 登录助手（auth skill 版）")
    parser.add_argument("--platform", required=True, choices=sorted(PLATFORMS), help="目标平台")
    parser.add_argument("--check-only", action="store_true", help="仅检查当前登录是否可复用")
    parser.add_argument("--timeout", type=int, default=300, help="等待登录超时时间（秒）")
    parser.add_argument("--project-root", default="", help="项目根目录；不传则默认取当前仓库")
    parser.add_argument("--notify-wechat", action="store_true", help="打开二维码后截图并发送到微信")
    args = parser.parse_args()

    global _PROJECT_ROOT_OVERRIDE
    if args.project_root:
        _PROJECT_ROOT_OVERRIDE = Path(args.project_root).expanduser().resolve()

    if args.check_only:
        ok, msg = check_platform_login(args.platform)
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
