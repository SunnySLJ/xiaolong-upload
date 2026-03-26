# 帧龙虾视频生成模块

## 说明

本目录用于存放帧龙虾 (zhenlongxia) 视频生成工具。

**当前状态：** check 分支已移除视频生成脚本 `zhenlongxia_workflow.py`

## 目录结构

```
flash_longxia/
├── .venv/              # Python 虚拟环境
├── output/             # 视频输出目录
└── token.txt           # 帧龙虾 API Token
```

## 使用方法

### 方案 1: 使用旧版本脚本

从 main 分支或其他备份中找回 `zhenlongxia_workflow.py`，放到此目录后执行：

```bash
cd /Users/mima0000/.openclaw/workspace/xiaolong-upload/flash_longxia
.venv/bin/python3 zhenlongxia_workflow.py /path/to/image.jpg
```

### 方案 2: 使用外部 API

直接使用帧龙虾 API 生成视频，然后手动保存到 `output/` 目录。

## Token 配置

编辑 `token.txt` 文件，填入你的帧龙虾 API Token。

**当前 Token:** `2993976a-b6d5-47a6-b19e-67bae05c1f82`

## 输出示例

生成的视频保存在：`flash_longxia/output/video_<timestamp>.mp4`

---

**最后更新：** 2026-03-26
