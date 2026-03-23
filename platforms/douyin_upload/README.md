# 抖音视频上传

抖音创作者平台视频上传工具，基于 nodriver（纯 CDP）。

## 文件结构

```
douyin_upload/
├── api.py             # 统一入口，外部调用 upload_to_douyin()
├── run_upload.py      # 脚本入口，修改参数后运行
├── conf.py            # 配置
├── douyin/
│   ├── __init__.py
│   ├── main.py        # 上传核心逻辑
│   └── browser.py     # Chrome 控制
├── utils/
│   ├── __init__.py
│   └── log.py         # 日志
├── scripts/
│   └── open_chrome_for_upload.sh   # connect 模式用
├── cookies/           # 运行时自动创建（profile/cookie 存放）
└── logs/              # 运行时自动创建
```

详见 `FILES.md` 获取完整文件清单。

## 使用步骤

1. **安装依赖**（在项目根目录）
   ```bash
   cd longxia_upload && pip install -r requirements.txt
   ```

2. **运行上传**  
   - 脚本方式：编辑 `run_upload.py` 中的 `VIDEO_FILE`、`TITLE`、`TAGS`，然后 `python run_upload.py`
   - 调用方式：`from douyin_upload.api import upload_to_douyin` 后调用 `upload_to_douyin(video_path, title, ...)`

3. **命令行**
   ```bash
   python api.py /path/to/video.mp4 "标题" "文案" "话题1,话题2"
   ```

4. **首次登录**  
   首次会打开 Chrome 要求扫码登录，登录态保存在 `cookies/default/`，之后无需重复登录。

## 登录模式（conf.py 中 AUTH_MODE）

| 模式 | 说明 |
|------|------|
| `profile`（默认） | 登录态保存在 cookies/default/ |
| `cookie` | 登录态保存为 JSON 文件 |
| `connect` | 连接已有 Chrome，需先运行 `scripts/open_chrome_for_upload.sh` |

## 环境变量

- `AUTH_MODE`：登录模式
- `LOCAL_CHROME_PATH`：Chrome 可执行文件路径
- `LOCAL_CHROME_HEADLESS`：是否无头模式
