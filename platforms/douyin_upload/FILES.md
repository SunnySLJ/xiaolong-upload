# 抖音上传项目 - 文件清单

## 必需文件（核心代码）

| 文件 | 说明 |
|------|------|
| `api.py` | **统一入口**，供外部调用 `upload_to_douyin()` |
| `conf.py` | 配置（Chrome 路径、登录模式等） |
| （根目录 `requirements.txt`） | 依赖统一在项目根 |
| `douyin/__init__.py` | 包标识 |
| `douyin/main.py` | 上传核心逻辑 |
| `douyin/browser.py` | Chrome 控制 |
| `utils/__init__.py` | 包标识 |
| `utils/log.py` | 日志模块 |

## 可选文件

| 文件 | 说明 |
|------|------|
| `run_upload.py` | 脚本入口，修改参数后直接运行 |
| `scripts/open_chrome_for_upload.sh` | AUTH_MODE=connect 时需先运行 |
| `README.md` | 使用说明 |

## 运行时生成（勿提交）

| 目录/文件 | 说明 |
|-----------|------|
| `.venv/` | 虚拟环境 |
| `cookies/` | 登录态（profile/cookie 模式） |
| `logs/` | 日志输出 |
| `__pycache__/` | Python 缓存 |

## 最小可迁移文件集

迁移到其他机器时，只需复制以下文件即可运行：

```
douyin_upload/
├── api.py
├── conf.py
├── douyin/
│   ├── __init__.py
│   ├── main.py
│   └── browser.py
└── utils/
    ├── __init__.py
    └── log.py
```

然后执行：
```bash
cd longxia_upload   # 项目根
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python api.py
```
