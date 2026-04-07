---
name: video-cleanup
slug: video-cleanup
version: 1.0.0
description: 自动清理已上传的视频文件，支持定时任务和手动清理。可配置保留天数和清理目录。
metadata:
  clawdbot:
    emoji: 🧹
    os: ["darwin", "linux"]
---

# 视频清理技能 (Video Cleanup)

自动清理已上传的视频文件，避免 output 目录积累大量文件，节省磁盘空间。

## 功能特性

- ✅ 支持定时清理（每天凌晨 1 点）
- ✅ 支持手动清理
- ✅ 可配置保留天数
- ✅ 详细的清理日志
- ✅ 安全的文件删除（只删除 .mp4 文件）

## 安装

### 方式 1: 本地安装（推荐）

将 skill 目录复制到 OpenClaw skills 目录：

```bash
cp -r /path/to/xiaolong-upload/skills/video-cleanup \
      ~/.local/node/lib/node_modules/openclaw/skills/
```

### 方式 2: 使用 clawhub（如果已发布）

```bash
clawhub install video-cleanup
```

## 配置

在 `config.yaml` 中配置（可选）：

```yaml
# 保留最近 N 天的视频
keep_days: 1

# 清理目录（相对于项目根目录）
output_dir: "flash_longxia/output"
```

默认配置：
- `keep_days`: 1 天
- `output_dir`: `flash_longxia/output`

## 使用方法

### 1. 手动清理

```bash
cd /path/to/xiaolong-upload
python3 scripts/cleanup_uploaded_videos.py
```

或使用 skill 命令：

```bash
clawhub run video-cleanup --manual
```

### 2. 定时清理

技能安装后会自动配置 Cron 任务，每天凌晨 1 点执行。

查看定时任务状态：

```bash
clawhub cron list
```

禁用定时任务：

```bash
clawhub cron disable video-cleanup
```

启用定时任务：

```bash
clawhub cron enable video-cleanup
```

## 清理规则

- **清理目录**: `flash_longxia/output/`
- **文件类型**: 仅清理 `.mp4` 文件
- **保留策略**: 保留最近 N 天的文件（默认 1 天）
- **执行时间**: 每天凌晨 1:00 (Asia/Shanghai)

## 日志输出示例

```
==================================================
[START] 视频清理任务启动
[START] 时间：2026-03-27 13:42:52
==================================================
[INFO] 开始清理视频文件
[INFO] 输出目录：/path/to/output
[INFO] 保留最近 1 天的文件
[INFO] 截止日期：2026-03-26 13:42:52
--------------------------------------------------
[DELETED] video_1774587071.mp4 (15.23 MB)
[DELETED] video_1774588123.mp4 (8.45 MB)
--------------------------------------------------
[SUMMARY] 清理完成
[SUMMARY] 删除文件数：2
[SUMMARY] 释放空间：23.68 MB
[SUMMARY] 执行时间：2026-03-27 13:42:52
==================================================
[SUCCESS] 清理任务完成
```

## 项目结构

```
xiaolong-upload/
├── scripts/
│   └── cleanup_uploaded_videos.py    # 清理脚本
├── skills/
│   └── video-cleanup/
│       └── SKILL.md                   # 技能文档
└── flash_longxia/
    └── output/                        # 清理目录
        └── *.mp4                      # 视频文件
```

## 注意事项

1. **首次安装**: 安装后会自动配置 Cron 任务
2. **保留天数**: 建议至少保留 1 天，避免误删刚生成的视频
3. **手动清理**: 发布视频后可以手动清理，释放空间
4. **日志查看**: 清理日志会输出到终端，方便排查问题

## 故障排查

### 问题 1: 找不到输出目录

**现象**: `[INFO] 输出目录不存在`

**解决**: 确认项目结构正确，`flash_longxia/output/` 目录存在

### 问题 2: 没有文件被清理

**现象**: `[SUMMARY] 删除文件数：0`

**解决**: 
- 确认视频文件超过保留天数
- 检查文件修改时间是否正确

### 问题 3: Cron 任务未执行

**现象**: 定时任务没有自动执行

**解决**:
```bash
# 查看 Cron 任务状态
clawhub cron list

# 重新启用任务
clawhub cron disable video-cleanup
clawhub cron enable video-cleanup
```

## 版本历史

### v1.0.0 (2026-03-27)
- 初始版本
- 支持手动清理
- 支持定时清理（Cron）
- 可配置保留天数
- 详细的清理日志
