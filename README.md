# 龙虾上传 - 四平台视频自助上传

整合抖音、快手、视频号、小红书的自动化上传能力，统一入口与共享配置。

## 平台一览

| 平台 | 目录 | 统一入口 | 标题限制 | 标签限制 |
|------|------|----------|----------|----------|
| 抖音 | `platforms/douyin_upload/` | `--platform douyin` | ≤30 字 | - |
| 快手 | `platforms/ks_upload/` | `--platform kuaishou` | ≤15 字 | ≤4 |
| 视频号 | `platforms/shipinhao_upload/` | `--platform shipinhao` | ≤64 字，可自动生成 | ≤10 |
| 小红书 | `platforms/xhs_upload/` | `--platform xiaohongshu` | ≤20 字 | ≤5 |

## 快速开始

### 环境

- Python 3.10+
- Google Chrome

### 安装

在项目根目录创建虚拟环境（需 Python 3.10+）：

```bash
cd /path/to/longxia_upload
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

若网络较慢，可用清华镜像：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

运行统一入口时使用根目录 Python：

```bash
.venv/bin/python upload.py -p kuaishou ...
# 或先激活：source .venv/bin/activate 后再 python upload.py ...
```

### 统一 CLI（推荐）

```bash
python upload.py --platform <平台> <视频路径> [标题] [文案] [标签]
```

示例：

```bash
# 抖音
python upload.py -p douyin /path/video.mp4 "记录生活" "美好的一天" "vlog,日常"

# 快手
python upload.py -p kuaishou video.mp4 "今日份快乐" "文案"

# 视频号（空标题/文案自动生成）
python upload.py -p shipinhao video.mp4 "" "" "生活记录,日常"

# 小红书
python upload.py -p xiaohongshu video.mp4 "标题" "文案" "标签1,标签2"
```

### 一键上传桌面视频

自动生成标题/文案/标签，默认桌面 `3.mp4`：

```bash
python scripts/upload_desktop.py -p kuaishou
python scripts/upload_desktop.py -p xiaohongshu /path/to/video.mp4
```

### 四平台顺序上传（抖音优先）

按 抖音 → 小红书 → 快手 → 视频号 依次上传同一视频（固定文案模板）：

```bash
python scripts/upload_xhs_ks_sph_generated.py C:\Users\你\Desktop\2.mp4
```

### 双击运行脚本（Windows）

使用根目录 `.venv`，传入参数给 `upload.py`：

- **Windows**：`scripts\run_upload.bat -p kuaishou 视频路径 "标题" "文案" "标签"`

### 各平台独立入口（可选）

```bash
cd platforms/douyin_upload && python upload_cli.py ...
cd platforms/ks_upload     && python upload.py ...
cd platforms/shipinhao_upload && python upload.py ...
cd platforms/xhs_upload    && python upload.py ...
```

## 项目结构

```
longxia_upload/
├── common/              # 共享模块
├── platforms/           # 各平台
│   ├── douyin_upload/
│   ├── ks_upload/
│   ├── shipinhao_upload/
│   └── xhs_upload/
├── scripts/             # 通用脚本（connect 上传、批量上传、Windows 启动器）
├── logs/                # 统一日志
├── cookies/             # 统一登录态（按平台分子目录）
├── upload.py            # 统一 CLI
└── requirements.txt
```

详见 [STRUCTURE.md](STRUCTURE.md)。

## 登录

首次运行会打开 Chrome 扫码/验证登录，登录态保存在 `cookies/<平台>/` 目录。

当前说明：

- “登录检查 / 补登录 / 巡检” 这条公共入口当前只支持视频号
- 四平台上传实现仍在仓库内，但不要再把 `scripts/platform_login.py` 视为其它平台的通用检查入口

环境变量：`AUTH_MODE`（profile/connect/cookie）、`LOCAL_CHROME_PATH`、`CDP_DEBUG_PORT` 等。

## 说明文档

- 登录与上传流程（权威）：`docs/LOGIN_FLOW.md`
