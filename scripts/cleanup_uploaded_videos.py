#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理已上传的视频文件
每天凌晨 1 点执行，清理 output 目录中超过 1 天的视频文件

支持 skill 方式调用：
- 手动清理：python3 scripts/cleanup_uploaded_videos.py --manual
- 定时清理：python3 scripts/cleanup_uploaded_videos.py (默认)
"""
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# 项目根目录（支持两种路径结构）
SCRIPT_DIR = Path(__file__).resolve().parent

# 尝试 xiaolong-upload 目录结构（脚本在 xiaolong-upload/scripts/）
if (SCRIPT_DIR.parent.parent / "openclaw_upload").exists():
    PROJECT_ROOT = SCRIPT_DIR.parent.parent / "openclaw_upload"
# 尝试直接在 openclaw_upload 下
elif (SCRIPT_DIR.parent / "flash_longxia").exists():
    PROJECT_ROOT = SCRIPT_DIR.parent
# 默认使用 workspace/openclaw_upload
else:
    PROJECT_ROOT = Path.home() / ".openclaw" / "workspace" / "openclaw_upload"

OUTPUT_DIR = PROJECT_ROOT / "flash_longxia" / "output"

# 保留最近 N 天的视频
KEEP_DAYS = 1


def cleanup_old_videos():
    """清理超过保留天数的视频文件"""
    if not OUTPUT_DIR.exists():
        print(f"[INFO] 输出目录不存在：{OUTPUT_DIR}")
        return
    
    # 计算保留的截止日期
    cutoff_time = datetime.now() - timedelta(days=KEEP_DAYS)
    cutoff_timestamp = cutoff_time.timestamp()
    
    deleted_count = 0
    deleted_size = 0
    
    print(f"[INFO] 开始清理视频文件")
    print(f"[INFO] 输出目录：{OUTPUT_DIR}")
    print(f"[INFO] 保留最近 {KEEP_DAYS} 天的文件")
    print(f"[INFO] 截止日期：{cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    # 遍历 output 目录
    for file_path in OUTPUT_DIR.glob("*.mp4"):
        try:
            file_mtime = file_path.stat().st_mtime
            
            # 如果文件修改时间早于截止日期，删除
            if file_mtime < cutoff_timestamp:
                file_size = file_path.stat().st_size
                file_name = file_path.name
                
                # 删除文件
                file_path.unlink()
                
                deleted_count += 1
                deleted_size += file_size
                
                print(f"[DELETED] {file_name} ({file_size / 1024 / 1024:.2f} MB)")
        except Exception as e:
            print(f"[ERROR] 处理文件失败 {file_path.name}: {e}")
    
    print("-" * 50)
    print(f"[SUMMARY] 清理完成")
    print(f"[SUMMARY] 删除文件数：{deleted_count}")
    print(f"[SUMMARY] 释放空间：{deleted_size / 1024 / 1024:.2f} MB")
    print(f"[SUMMARY] 执行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    global KEEP_DAYS
    
    parser = argparse.ArgumentParser(
        description="清理已上传的视频文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 cleanup_uploaded_videos.py              # 定时清理模式
  python3 cleanup_uploaded_videos.py --manual     # 手动清理模式
  python3 cleanup_uploaded_videos.py --keep 7     # 保留 7 天
        """
    )
    parser.add_argument("--manual", action="store_true", help="手动清理模式")
    parser.add_argument("--keep", type=int, default=KEEP_DAYS, help=f"保留最近 N 天的文件 (默认：{KEEP_DAYS})")
    args = parser.parse_args()
    
    KEEP_DAYS = args.keep
    
    mode = "手动" if args.manual else "定时"
    print("=" * 50)
    print(f"[START] 视频清理任务启动 ({mode}模式)")
    print(f"[START] 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[START] 保留天数：{KEEP_DAYS} 天")
    print("=" * 50)
    
    try:
        cleanup_old_videos()
        print("=" * 50)
        print(f"[SUCCESS] 清理任务完成")
        sys.exit(0)
    except Exception as e:
        print("=" * 50)
        print(f"[ERROR] 清理任务失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
