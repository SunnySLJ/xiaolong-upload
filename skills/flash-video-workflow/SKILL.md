---
name: flash-video-workflow
description: 本地图片转视频工作流原型技能。当用户明确提到“flash-video-workflow”“本仓库里的图生视频工作流原型”“检查或修这个 workflow 脚本”时使用。负责查看 `skills/flash-video-workflow/scripts/` 下的本地原型脚本，并在执行前先核对硬编码路径和依赖。
---

# Flash Video Workflow

这是仓库内保留的一套本地工作流原型，不是当前会话里注册的正式 `flash-longxia` skill。

## 当前定位

- 目录：`skills/flash-video-workflow/`
- 脚本：
  - `skills/flash-video-workflow/scripts/workflow.py`
  - `skills/flash-video-workflow/scripts/run_workflow.py`
- 用途：查看、调试、重构这套原型脚本
- 共享路径配置：`skills/runtime_config.json`

## 重要限制

1. 这套脚本包含硬编码工作区路径，运行前必须先核对本机目录是否匹配。
2. 其中引用的外部工作流和 API 并不是当前仓库的权威接口，不能直接当成生产流程说明。
3. 若用户要真正跑图生视频任务，优先使用当前会话里注册的 `flash-longxia` skill，而不是这份本地原型文档。

## 适合处理的请求

- “看看这个 flash-video-workflow 还能不能用”
- “修一下 workflow.py 里的路径/轮询逻辑”
- “把这套原型改成和当前项目一致”

## 不适合直接照做的内容

- 不要直接相信文档里写死的工作区路径
- 不要直接相信文档里写死的外部 API 地址
- 不要把它当成发布流程的权威说明

## 调试入口

查看帮助或快速试跑：

```bash
/opt/homebrew/bin/python3.12 skills/flash-video-workflow/scripts/run_workflow.py "<image_path>"
```

在真正运行前，先检查：

- `workflow.py` 里写死的目录
- 依赖的外部脚本是否存在
- 生成、轮询、下载三个阶段是否仍匹配当前项目

## 与正式流程的关系

- 图片生成视频：优先走正式 `flash-longxia`
- 多平台发布：走 `longxia-upload`
- 平台补登录：走 `auth`
