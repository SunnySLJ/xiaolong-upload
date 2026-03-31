#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flash-video-workflow 快速启动脚本
用法：
  python3 run_workflow.py <图片路径> [model] [aspectRatio] [duration]
"""

import sys
import os

# 添加脚本目录到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from workflow import (
    workflow_receive_image,
    workflow_confirm_params,
    workflow_generate,
    workflow_poll,
    workflow_confirm_publish,
    workflow_publish,
    DEFAULT_PARAMS
)


def main():
    if len(sys.argv) < 2:
        print("用法：python3 run_workflow.py <图片路径> [model] [aspectRatio] [duration]")
        print(f"默认参数：model={DEFAULT_PARAMS['model']}, aspectRatio={DEFAULT_PARAMS['aspectRatio']}, duration={DEFAULT_PARAMS['duration']}")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    # 解析参数
    params = DEFAULT_PARAMS.copy()
    if len(sys.argv) > 2:
        params['model'] = sys.argv[2]
    if len(sys.argv) > 3:
        params['aspectRatio'] = sys.argv[3]
    if len(sys.argv) > 4:
        params['duration'] = int(sys.argv[4])
    
    print("=" * 50)
    print("📹 视频生成工作流")
    print("=" * 50)
    
    # 阶段 1: 确认参数
    print(workflow_confirm_params(params))
    
    # 等待用户确认（这里只是示例，实际由主程序处理）
    print("\n⚠️  注意：实际使用时需要等待用户确认后再调用 workflow_generate()")
    
    # 示例：生成视频
    # task_id = workflow_generate(image_path, params)
    # print(f"任务 ID: {task_id}")
    
    # 阶段 3: 启动轮询
    # def on_video_ready(video_path):
    #     print(f"视频已完成：{video_path}")
    #     print(workflow_confirm_publish())
    # 
    # workflow_poll(task_id, on_video_ready)
    
    print("\n工作流已初始化，等待用户确认...")


if __name__ == "__main__":
    main()
