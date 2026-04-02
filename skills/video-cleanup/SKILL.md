---
name: video-cleanup
description: 自动清理已上传或已生成的视频文件。当用户提到“清理视频”“删除旧视频”“定时清理 output 视频”“保留最近几天的视频”时使用。负责调用仓库内清理脚本并明确回传清理目录、保留天数和删除结果。
---

# Video Cleanup Skill

本技能负责清理旧的 `.mp4` 文件，不处理上传、登录或任务调度。

## 入口

- 脚本：`scripts/cleanup_uploaded_videos.py`
- 当前默认清理目录：脚本解析出的 `flash_longxia/output`
- 默认保留天数：`1`
- 共享路径配置：`skills/runtime_config.json`

## 标准命令

手动清理：

```bash
/opt/homebrew/bin/python3.12 scripts/cleanup_uploaded_videos.py --manual
```

保留最近 7 天：

```bash
/opt/homebrew/bin/python3.12 scripts/cleanup_uploaded_videos.py --manual --keep 7
```

按默认模式执行一次：

```bash
/opt/homebrew/bin/python3.12 scripts/cleanup_uploaded_videos.py
```

直接指定目录：

```bash
/opt/homebrew/bin/python3.12 scripts/cleanup_uploaded_videos.py --manual --output-dir "/abs/path/to/output"
```

## 执行规则

1. 先告诉用户将清理哪个目录、保留多少天。
2. 只删除 `.mp4` 文件，不扩展到其它业务文件。
3. 若输出目录不存在，按脚本原样回传，不自行创建或删除别的目录。
4. 若用户要“定时清理”，说明该脚本本身只负责单次执行；调度应交给外部定时器。

## 回传要求

结果至少包含：

- 实际清理目录
- 保留天数
- 删除文件数
- 释放空间
- 是否执行成功
