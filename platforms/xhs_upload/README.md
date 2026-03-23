# 小红书视频上传 (xhs_upload)

小红书创作者平台视频上传工具，纯 CDP 实现（nodriver）。**Mac / Windows 兼容**。

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

| 系统 | 操作 |
|------|------|
| **Mac** | 双击 `run_upload_mac.command`，或在终端执行后跟参数 |
| **Windows** | 双击 `run_upload.bat`，或在 CMD 中执行后跟参数 |

首次运行会自动创建虚拟环境并安装依赖。

## 文件结构

```
xhs_upload/
├── upload.py          # 统一上传入口（推荐）
├── upload_desktop.py  # 桌面视频 + 自动生成文案
├── api.py             # 底层 API
├── pyproject.toml     # 项目配置（Python >= 3.10）
├── conf.py            # 配置（Mac/Windows 自动检测 Chrome）
└── xiaohongshu/       # 上传逻辑
```

## 参数说明

- **标题**：最多 20 字
- **标签**：最多 5 个，逗号分隔
- **文案**：可选，留空可传 `""`

## 环境变量

- `AUTH_MODE`：profile（默认）/ cookie / connect
- `LOCAL_CHROME_PATH`：Chrome 可执行路径（不设则自动检测）
- `LOCAL_CHROME_HEADLESS`：是否无头模式
- `CHROME_USER_DATA_DIR`：Chrome 用户数据目录
