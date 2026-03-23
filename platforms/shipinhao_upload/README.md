# 视频号自动化上传

微信视频号助手网页版自动化上传工具，支持自动填标题、文案、话题。

## 环境

- Python 3.10+
- Google Chrome

## 安装

在项目根目录执行：
```bash
pip install -r requirements.txt
```

## 使用

```bash
# 命令行
python upload.py <视频路径> [标题] [文案] [标签1,标签2,...]

# 示例
python upload.py /path/to/video.mp4 "今日份快乐" "美好的一天 ✨" "生活记录,日常,vlog"

# 自动生成标题和文案（传空）
python upload.py video.mp4 "" "" "生活记录,日常分享"
```

```python
# API
from upload import upload

upload(
    video_path="/path/to/video.mp4",
    title="标题",
    description="文案",
    tags=["生活记录", "日常"],
)
```

## 登录

首次运行会打开 Chrome，请用**微信扫码**登录视频号助手。登录态会保存在 `cookies/` 目录。

### 复用已登录的 Chrome

若 Chrome 已打开且已登录，可用调试端口启动后复用：

```bash
# Mac
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome_sph

# 然后运行上传
python upload.py video.mp4 "标题" "文案" "标签"
```

## 项目结构

```
shipinhao_upload/
├── upload.py       # 入口（CLI + API）
├── conf.py         # 配置
├── shipinhao/      # 核心逻辑
│   ├── main.py     # 上传流程
│   └── browser.py  # 浏览器
├── utils/
│   └── log.py
└── cookies/        # 登录态（已统一到根 cookies/shipinhao/）
```

## 环境变量

- `AUTH_MODE`：profile（默认）/ cookie / connect
- `LOCAL_CHROME_PATH`：Chrome 路径
- `CDP_DEBUG_PORT`：调试端口，默认 9222
