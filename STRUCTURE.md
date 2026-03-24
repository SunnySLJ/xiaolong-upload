# 龙虾上传 - 项目结构说明

## 一、总体结构

```
longxia_upload/
├── common/                  # 共享模块
│   ├── conf.py             # Chrome、Auth 等配置
│   ├── log.py              # 日志工厂
│   ├── loggers.py          # 各平台 logger 统一导出
│   ├── browser.py          # nodriver 启动
│   └── utils.py            # 工具函数
├── platforms/               # 各平台实现
│   ├── douyin_upload/
│   ├── ks_upload/
│   ├── shipinhao_upload/
│   └── xhs_upload/
├── scripts/                 # 通用脚本
│   ├── open_chrome_for_upload.ps1
│   ├── run_upload.bat
│   ├── upload_desktop.py                  # 单平台上传（自动生成文案）
│   ├── upload_xhs_ks_sph_generated.py     # 四平台队列（抖音优先）
│   ├── upload_douyin_connect.ps1
│   ├── upload_xiaohongshu_connect.ps1
│   ├── upload_kuaishou_connect.ps1
│   └── upload_shipinhao_connect.ps1
├── skills/                  # Cursor Agent Skills（如 douyin-upload）
├── logs/                    # 统一日志（logs/douyin.log 等）
├── cookies/                 # 统一登录态
│   ├── douyin/
│   ├── kuaishou/
│   ├── shipinhao/
│   ├── xiaohongshu/
│   └── chrome_connect/      # connect 模式用
├── upload.py               # 统一 CLI 入口
└── requirements.txt
```

## 二、平台目录结构

每个平台（如 `platforms/ks_upload/`）包含：

```
ks_upload/
├── api.py           # upload_to_kuaishou()
├── upload.py        # 平台 CLI（供 cd 进目录时用）
├── conf.py          # 平台配置（引用 common）
└── kuaishou/        # 核心逻辑
    ├── main.py
    └── browser.py
```

## 三、整合说明

- **依赖**：统一使用根目录 `requirements.txt`，已移除各平台 requirements.txt
- **日志**：统一写入 `logs/`，由 `common/loggers.py` 管理
- **cookies**：统一存于 `cookies/<平台>/`，首次运行自动创建
- **scripts**：统一在 `scripts/`，含 connect 上传脚本、批量上传脚本、Windows 启动器
- **utils**：已移除各平台 utils/，统一使用 `common.loggers`
- **权威流程文档**：登录与上传流程统一参考 `docs/LOGIN_FLOW.md`
