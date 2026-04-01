#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flash-video-workflow - 完整的图片生成视频并发布工作流
"""

import os
import sys
import json
import time
import subprocess
import threading
import shutil
from datetime import datetime
from pathlib import Path

# 工作目录
WORKSPACE = Path("/Users/mima0000/.openclaw/workspace")
INBOUND_IMAGES = WORKSPACE / "inbound_images"
FLASH_LONGXIA = WORKSPACE / "openclaw_upload" / "flash_longxia"
OUTPUT_DIR = FLASH_LONGXIA / "output"
PENDING_TASKS = FLASH_LONGXIA / "pending_tasks.json"
XIAOLONG_UPLOAD = WORKSPACE / "xiaolong-upload"
UPLOAD_SCRIPT = XIAOLONG_UPLOAD / "upload.py"
AUTH_SCRIPT = XIAOLONG_UPLOAD / "skills" / "auth" / "scripts" / "platform_login.py"
QR_DIR = XIAOLONG_UPLOAD / "logs" / "auth_qr"

# 确保目录存在
for dir_path in [INBOUND_IMAGES, OUTPUT_DIR, QR_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# 默认参数
DEFAULT_PARAMS = {
    "model": "auto",
    "aspectRatio": "9:16",
    "duration": 10
}

# 默认发布信息
DEFAULT_POST = {
    "title": "可爱日常 ✨",
    "caption": "元气满满的日常记录～ 每一天都值得被记录 📸💕",
    "tags": "可爱，日常，生活记录"
}


def save_image(image_data, filename):
    """保存图片到 inbound_images 目录"""
    import base64
    
    # 如果是 base64 数据
    if isinstance(image_data, str) and image_data.startswith('data:'):
        # 提取 base64 部分
        header, data = image_data.split(',', 1)
        image_bytes = base64.b64decode(data)
    else:
        image_bytes = image_data
    
    filepath = INBOUND_IMAGES / filename
    with open(filepath, 'wb') as f:
        f.write(image_bytes)
    
    return str(filepath)


def load_pending_tasks():
    """加载待处理任务"""
    if PENDING_TASKS.exists():
        with open(PENDING_TASKS, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"tasks": []}


def save_pending_tasks(tasks_data):
    """保存待处理任务"""
    with open(PENDING_TASKS, 'w', encoding='utf-8') as f:
        json.dump(tasks_data, f, ensure_ascii=False, indent=2)


def generate_video(image_path, params=None):
    """调用视频生成接口"""
    if params is None:
        params = DEFAULT_PARAMS
    
    cmd = [
        "python3",
        str(FLASH_LONGXIA / "zhenlongxia_workflow.py"),
        image_path,
        f"--model={params['model']}",
        f"--aspectRatio={params['aspectRatio']}",
        f"--duration={params['duration']}"
    ]
    
    print(f"执行命令：{' '.join(cmd)}")
    
    # 执行生成命令
    result = subprocess.run(cmd, cwd=str(FLASH_LONGXIA), capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"生成失败：{result.stderr}")
        return None
    
    # 从输出中提取任务 ID（需要根据实际输出格式调整）
    # 假设输出中包含 "task_id: 1234" 或类似格式
    output = result.stdout
    task_id = None
    
    # 尝试从输出中提取任务 ID
    for line in output.split('\n'):
        if 'task_id' in line.lower() or '任务 ID' in line:
            # 提取数字
            import re
            match = re.search(r'\d+', line)
            if match:
                task_id = match.group()
                break
    
    # 如果没找到任务 ID，使用时间戳作为临时 ID
    if not task_id:
        task_id = str(int(time.time()))
    
    return task_id


def poll_task_status(task_id, base_url, token, callback=None):
    """轮询任务状态"""
    import requests
    
    max_attempts = 60  # 30 分钟，每 30 秒一次
    attempt = 0
    
    while attempt < max_attempts:
        time.sleep(30)
        attempt += 1
        
        try:
            # 查询任务状态
            response = requests.get(
                f"{base_url}/api/task/{task_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status', '')
                
                if status == 'completed':
                    # 视频生成完成
                    video_url = data.get('video_url')
                    if video_url and callback:
                        callback(task_id, video_url)
                    return True
                elif status == 'failed':
                    print(f"任务 {task_id} 生成失败")
                    return False
                # 其他状态继续轮询
                print(f"任务 {task_id} 状态：{status} (第{attempt}次查询)")
        except Exception as e:
            print(f"查询失败：{e}")
    
    print(f"任务 {task_id} 轮询超时")
    return False


def download_video(task_id, video_url):
    """下载视频到 output 目录"""
    import requests
    
    output_path = OUTPUT_DIR / f"{task_id}.mp4"
    
    response = requests.get(video_url, stream=True)
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return str(output_path)
    return None


def check_platform_login(platform):
    """检查平台登录状态"""
    cmd = [
        "/opt/homebrew/bin/python3.12",
        str(AUTH_SCRIPT),
        "--platform", platform,
        "--check-only"
    ]
    
    result = subprocess.run(cmd, cwd=str(XIAOLONG_UPLOAD), capture_output=True, text=True)
    return "已登录" in result.stdout or "logged in" in result.stdout.lower()


def get_platform_qr(platform):
    """获取平台登录二维码"""
    cmd = [
        "/opt/homebrew/bin/python3.12",
        str(AUTH_SCRIPT),
        "--platform", platform,
        "--notify-wechat"
    ]
    
    subprocess.run(cmd, cwd=str(XIAOLONG_UPLOAD))
    
    # 返回二维码路径
    qr_path = QR_DIR / f"{platform}_login_qr.png"
    return str(qr_path) if qr_path.exists() else None


def upload_video(platform, video_path, title, caption, tags):
    """上传视频到指定平台"""
    cmd = [
        "/opt/homebrew/bin/python3.12",
        str(UPLOAD_SCRIPT),
        "-p", platform,
        video_path,
        title,
        caption,
        tags
    ]
    
    print(f"上传到 {platform}: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, cwd=str(XIAOLONG_UPLOAD), capture_output=True, text=True)
    
    success = "成功" in result.stdout or "success" in result.stdout.lower()
    return success, result.stdout


def start_polling_thread(task_id, base_url, token, video_path_callback):
    """启动后台轮询线程"""
    def poll_and_download():
        success = poll_task_status(task_id, base_url, token)
        if success:
            # 下载视频
            video_url = f"http://{base_url}/video/{task_id}.mp4"
            video_path = download_video(task_id, video_url)
            if video_path and video_path_callback:
                video_path_callback(video_path)
    
    thread = threading.Thread(target=poll_and_download, daemon=True)
    thread.start()
    return thread


# ============ 主流程函数 ============

def workflow_receive_image(image_data, filename):
    """阶段 1: 接收图片"""
    image_path = save_image(image_data, filename)
    print(f"图片已保存：{image_path}")
    return image_path


def workflow_confirm_params(params=None):
    """阶段 1: 确认参数"""
    if params is None:
        params = DEFAULT_PARAMS
    
    confirm_msg = f"""
📹 **视频生成参数确认**

- **模型**: {params.get('model', 'auto')}
- **画面比例**: {params.get('aspectRatio', '9:16')}
- **视频时长**: {params.get('duration', 10)} 秒

请回复 "**确定生成**" 或 "**确认生成**" 开始生成视频。
如需修改参数，请告诉我具体要改什么。
"""
    return confirm_msg


def workflow_generate(image_path, params=None):
    """阶段 2: 生成视频"""
    task_id = generate_video(image_path, params)
    
    if task_id:
        # 记录任务
        tasks_data = load_pending_tasks()
        tasks_data["tasks"].append({
            "task_id": task_id,
            "image_path": image_path,
            "params": params or DEFAULT_PARAMS,
            "created_at": datetime.now().isoformat(),
            "status": "generating"
        })
        save_pending_tasks(tasks_data)
        
        return task_id
    return None


def workflow_poll(task_id, callback):
    """阶段 3: 启动轮询"""
    # 这里需要根据实际 API 配置 base_url 和 token
    base_url = "http://123.56.58.223:8081"
    token = "4ff2c1aa-384a-4c48-8fc1-e674c5f65219"
    
    def on_video_ready(video_path):
        # 更新任务状态
        tasks_data = load_pending_tasks()
        for task in tasks_data["tasks"]:
            if task["task_id"] == task_id:
                task["status"] = "completed"
                task["video_path"] = video_path
                break
        save_pending_tasks(tasks_data)
        
        if callback:
            callback(video_path)
    
    thread = start_polling_thread(task_id, base_url, token, on_video_ready)
    return thread


def workflow_confirm_publish():
    """阶段 4: 确认发布"""
    confirm_msg = """
🎉 **视频生成完成！**

视频已发送给你，请查看。

请回复：
- "**确认发布**" 或 "**可以发布**" 开始上传
- 并告诉我要发布到哪些平台（抖音/快手/小红书/视频号/全部）

默认发布信息：
- **标题**: 可爱日常 ✨
- **文案**: 元气满满的日常记录～ 每一天都值得被记录 📸💕
- **标签**: #可爱 #日常 #生活记录
"""
    return confirm_msg


def workflow_publish(video_path, platforms, title=None, caption=None, tags=None):
    """阶段 5: 多平台发布"""
    if title is None:
        title = DEFAULT_POST["title"]
    if caption is None:
        caption = DEFAULT_POST["caption"]
    if tags is None:
        tags = DEFAULT_POST["tags"]
    
    # 平台顺序
    platform_order = ["douyin", "xiaohongshu", "kuaishou", "shipinhao"]
    platform_names = {
        "douyin": "抖音",
        "xiaohongshu": "小红书",
        "kuaishou": "快手",
        "shipinhao": "视频号"
    }
    
    results = []
    
    # 如果发布全部
    if "全部" in platforms or "all" in platforms.lower():
        platforms = platform_order
    else:
        # 转换中文平台名为英文
        platform_map = {
            "抖音": "douyin",
            "快手": "kuaishou",
            "小红书": "xiaohongshu",
            "视频号": "shipinhao"
        }
        platforms = [platform_map.get(p, p) for p in platforms]
    
    for platform in platform_order:
        if platform not in platforms and "全部" not in platforms:
            continue
        
        name = platform_names.get(platform, platform)
        
        # 检查登录状态
        if not check_platform_login(platform):
            # 获取二维码
            qr_path = get_platform_qr(platform)
            results.append({
                "platform": name,
                "status": "need_login",
                "qr_path": qr_path
            })
            continue
        
        # 上传视频
        success, output = upload_video(platform, video_path, title, caption, tags)
        results.append({
            "platform": name,
            "status": "success" if success else "failed",
            "output": output
        })
    
    return results


# ============ 测试 ============

if __name__ == "__main__":
    print("flash-video-workflow 技能模块")
    print(f"工作目录：{WORKSPACE}")
    print(f"图片目录：{INBOUND_IMAGES}")
    print(f"视频输出：{OUTPUT_DIR}")
