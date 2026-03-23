---
name: douyin-upload
description: Upload videos to Douyin (抖音) creator platform. Use when the user says "帮我上传" with video path, title, description, and tags. Supports Mac and Windows. Parses natural language like "上传 X 视频，标题 Y，文案 Z，标签 A,B,C".
---

# 抖音上传

当用户说「帮我上传」「上传视频」并给出视频路径、标题、文案、标签时，执行抖音上传。

## 触发示例

- "帮我上传 /path/to/video.mp4，标题：记录生活，文案：美好的一天，标签：vlog,日常"
- "上传这个视频，标题 xxx，文案 xxx，标签 a,b,c"
- "帮我上传哪个视频，标题和文案、标签是什么" → 向用户确认缺少的参数

## 执行流程

1. **解析参数**：从用户消息提取 `video_path`、`title`、`description`、`tags`
2. **确认缺失项**：若缺少必填项（视频路径、标题），向用户确认
3. **定位项目**：项目根目录 `longxia_upload/`（如 `~/Desktop/ai-shuang/longxia_upload` 或当前工作区）
4. **执行上传**（跨平台）：

Mac/Linux:
```bash
cd <项目根目录> && .venv/bin/python upload.py -p douyin "<video_path>" "<title>" "<description>" "<tags>"
```

Windows:
```bash
cd <项目根目录> && .venv\Scripts\python upload.py -p douyin "<video_path>" "<title>" "<description>" "<tags>"
```

若无 `.venv` 用 `python3`（需 Python 3.10+）。

## 参数格式

| 参数 | 必填 | 说明 |
|------|------|------|
| video_path | 是 | 视频文件绝对或相对路径 |
| title | 是 | 标题，最多 30 字 |
| description | 否 | 视频描述/文案，默认空 |
| tags | 否 | 话题标签，逗号分隔，如 "vlog,日常" |

## 首次使用

- **profile 模式**（默认）：首次会打开浏览器扫码登录，登录态保存在项目 cookies
- **需 Chrome**：确保已安装 Google Chrome
- **Mac**：Chrome 路径自动检测
- **Windows**：Chrome 默认 `C:\Program Files\Google\Chrome\Application\chrome.exe`，可通过环境变量 `LOCAL_CHROME_PATH` 覆盖

## 项目结构

```
longxia_upload/
├── upload.py       # 统一入口，upload.py -p douyin ...
├── platforms/
│   └── douyin_upload/
│       └── api.py  # upload_to_douyin()
├── cookies/douyin/ # 登录态
└── scripts/        # open_chrome_for_upload.sh (connect 模式用)
```

## 常见项目路径

- `~/Desktop/ai-shuang/longxia_upload`
- 当前工作区根目录
- **OpenClaw 下执行时设置 `DOUYIN_DETACH_BROWSER=1`**，否则任务结束后会关闭浏览器。

## 回应用户

执行后简要说明：成功/失败，以及错误原因（若失败）。
