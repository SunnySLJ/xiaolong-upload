#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
登录失效通知工具 - 截图并发送微信通知给用户

用法:
    python notify_login_qr.py shipinhao <截图路径>
    python notify_login_qr.py douyin <截图路径>
    ...
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

PLATFORM_NAMES = {
    "douyin": "抖音",
    "kuaishou": "快手",
    "shipinhao": "视频号",
    "xiaohongshu": "小红书",
}


def send_wechat_notification(platform: str, screenshot_path: str):
    """发送微信通知给用户，附带登录二维码截图"""
    platform_name = PLATFORM_NAMES.get(platform, platform)
    
    # 检查截图文件是否存在
    if not os.path.exists(screenshot_path):
        print(f"错误：截图文件不存在：{screenshot_path}")
        return False
    
    # 通过 OpenClaw message 工具发送
    # 这里调用 OpenClaw 的 message 工具发送图片
    try:
        import subprocess
        import json
        
        # 使用 openclaw message 命令发送图片
        cmd = [
            "openclaw", "message", "send",
            "--channel", "openclaw-weixin",
            "--media", screenshot_path,
            "--message", f"🔔 {platform_name}登录已失效\n\n请打开图片微信扫码登录，登录成功后会自动继续上传～"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print(f"✅ 微信通知已发送：{platform_name}登录二维码")
            return True
        else:
            print(f"❌ 发送失败：{result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 发送异常：{e}")
        return False


def main():
    if len(sys.argv) < 3:
        print("用法：python notify_login_qr.py <平台> <截图路径>")
        print("平台：douyin | kuaishou | shipinhao | xiaohongshu")
        sys.exit(1)
    
    platform = sys.argv[1].lower()
    screenshot_path = sys.argv[2]
    
    if platform not in PLATFORM_NAMES:
        print(f"错误：未知平台：{platform}")
        sys.exit(1)
    
    success = send_wechat_notification(platform, screenshot_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
