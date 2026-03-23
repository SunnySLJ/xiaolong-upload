# 快手视频上传 (ks_upload)

快手创作者平台视频上传工具，纯 CDP 实现（nodriver）。**Mac / Windows 兼容**。

## 环境要求

- **Python 3.10+**（nodriver 依赖）
- Google Chrome
- 已安装依赖：在项目根目录执行 `pip install -r requirements.txt`

## 统一上传入口

传入 **视频路径、标题、文案、标签** 即可上传：

```bash
python upload.py <视频路径> <标题> [文案] [标签1,标签2,...]
```

**示例：**
```bash
# Mac
python upload.py /Users/xxx/Desktop/3.mp4 "今日份快乐" "美好的一天 ✨" "生活记录,日常,vlog"

# Windows
python upload.py D:\videos\a.mp4 "今日份快乐" "美好的一天 ✨" "生活记录,日常,vlog"
```

**桌面视频一键上传：**
```bash
python scripts/upload_desktop.py -p kuaishou
```

**API 调用：**
```python
from upload import upload

upload(
    video_path="/path/to/video.mp4",
    title="今日份快乐",
    description="美好的一天 ✨",
    tags=["生活记录", "日常", "vlog"],
)
```

## 快速启动（双击运行）

使用根目录统一脚本：`scripts/run_upload_mac.command` 或 `scripts/run_upload.bat`，传入 `-p kuaishou` 及视频路径等参数。

## 文件结构

```
ks_upload/
├── upload.py          # 平台 CLI（cd 进目录时用）
├── api.py             # 底层 API
├── pyproject.toml     # 项目配置（Python >= 3.10）
├── conf.py            # 配置（Mac/Windows 自动检测 Chrome）
└── kuaishou/          # 上传逻辑
```

## 参数说明

- **标题**：最多 15 字（快手限制）
- **标签**：最多 4 个，逗号分隔，填充时自动加 #
- **文案**：可选，留空可传 `""`

## 环境变量

- `AUTH_MODE`：profile（默认）/ cookie / connect
- `LOCAL_CHROME_PATH`：Chrome 可执行路径（不设则自动检测）
- `LOCAL_CHROME_HEADLESS`：是否无头模式
- `CHROME_USER_DATA_DIR`：Chrome 用户数据目录

## OpenClaw 同步

OpenClaw 使用本地副本 `~/.openclaw/workspace/ks-auto-uploader`。本仓库更新后需手动同步：

```bash
rsync -av --exclude='.venv' --exclude='__pycache__' --exclude='logs' --exclude='.git' \
  /Users/h/Desktop/ai-shuang/ks_upload/ ~/.openclaw/workspace/ks-auto-uploader/
```
