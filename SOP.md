# OpenClaw 智能视频发布系统 - 标准操作流程 (SOP)

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 系统名称 | OpenClaw 智能视频发布系统（龙虾上传） |
| 文档版本 | v1.0 |
| 最后更新 | 2026-03-31 |
| 适用平台 | 抖音、快手、小红书、视频号 |

---

## 🎯 一、系统概述

### 1.1 核心功能

OpenClaw 是一套基于 AI 助手的智能视频发布系统，通过微信交互实现视频从生成到发布的全流程自动化：

| 功能模块 | 说明 |
|---------|------|
| **图生视频** | 用户上传 1-4 张图片，AI 调用帧龙虾 API 自动生成视频 |
| **多平台登录管理** | 自动检测抖音、快手、小红书、视频号登录状态，失效时生成二维码登录 |
| **多平台视频发布** | 登录成功后，将视频发布到四个平台，支持标题/文案/标签自动填充 |
| **文件管理** | 自动接收用户上传图片/视频，分类存储，定期清理 |

### 1.2 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户交互层                                │
│                    微信 (OpenClaw-Weixin)                        │
│              发送图片 → AI → 接收视频/二维码/状态                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        AI 核心层 (OpenClaw)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Memory     │  │   Skills     │  │    Cron      │          │
│  │  记忆管理    │  │   技能调用   │  │   定时任务   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        执行层                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ flash-longxia│  │    auth      │  │ longxia-     │          │
│  │   图生视频   │  │   登录管理   │  │   upload     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        平台层                                    │
│    抖音    │    快手    │    小红书    │    视频号               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 二、部署流程

### 2.1 环境要求

| 组件 | 版本要求 | 说明 |
|------|---------|------|
| 操作系统 | macOS / Windows | macOS 推荐 13+，Windows 推荐 10+ |
| Python | **3.12** | ⚠️ **必须 3.12**，macOS 可通过 Homebrew 安装 |
| Google Chrome | 最新版 | 用于平台登录和上传 |
| OpenClaw | >=2026.3.22 | AI 助手运行环境 |
| 微信 | 最新版 | 用于用户交互 |

### 2.2 安装步骤

#### 步骤 1：安装 OpenClaw 核心

```bash
# 安装 OpenClaw
npm install -g openclaw

# 验证安装
openclaw --version
```

#### 步骤 2：安装微信渠道插件

```bash
# 一键安装微信插件
npx -y @tencent-weixin/openclaw-weixin-cli install

# 或手动安装
openclaw plugins install "@tencent-weixin/openclaw-weixin"
openclaw config set plugins.entries.openclaw-weixin.enabled true
```

#### 步骤 3：绑定微信账号

```bash
# 扫码登录微信
openclaw channels login --channel openclaw-weixin

# 重启 gateway
openclaw gateway restart
```

#### 步骤 4：安装技能

将以下技能复制到 OpenClaw 技能目录：

```bash
# 技能目录结构
~/.openclaw/skills/
├── flash-longxia/          # 图生视频技能
├── auth/                   # 登录管理技能
└── longxia-upload/         # 上传发布技能
```

#### 步骤 5：配置上传项目

```bash
# 克隆或复制上传项目到工作区
cp -r /path/to/xiaolong-upload ~/.openclaw/workspace/

# 安装依赖（必须使用 Python 3.12）
cd ~/.openclaw/workspace/xiaolong-upload
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**⚠️ 注意**：必须使用 Python 3.12，其他版本可能导致兼容性问题。

#### 步骤 6：配置定时任务

```bash
# 编辑 cron 配置
# ~/.openclaw/cron/jobs.json

# 关键任务：
# 1. 视频清理：每周二凌晨 1:00 执行
# 2. 登录检查：每天上午 10:10 执行
```

### 2.3 目录结构

```
~/.openclaw/
├── openclaw.json                    # 核心配置文件
├── skills/                          # 技能目录
│   ├── flash-longxia/              # 图生视频技能
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       ├── generate_video.py   # 视频生成脚本
│   │       └── download_video.py   # 视频下载脚本
│   ├── auth/                       # 登录管理技能
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── platform_login.py   # 平台登录脚本
│   └── longxia-upload/             # 上传发布技能
│       ├── SKILL.md
│       └── scripts/
├── workspace/
│   └── xiaolong-upload/            # 上传项目
│       ├── upload.py               # 统一上传入口
│       ├── platforms/              # 各平台模块
│       │   ├── douyin_upload/
│       │   ├── kuaishou_upload/
│       │   ├── xiaohongshu_upload/
│       │   └── shipinhao_upload/
│       ├── cookies/                # 登录态存储
│       │   ├── chrome_connect_dy   # 抖音
│       │   ├── chrome_connect_ks   # 快手
│       │   ├── chrome_connect_xhs  # 小红书
│       │   └── chrome_connect_sph  # 视频号
│       └── logs/                   # 运行日志
├── media/
│   └── inbound/                    # 用户发送的文件
└── cron/
    └── jobs.json                   # 定时任务配置
```

---

## 📱 三、用户交互流程

### 3.1 图生视频功能

**用户操作流程：**

```
1. 用户在微信中发送 1-4 张图片给 OpenClaw
2. OpenClaw 调用 flash-longxia 技能生成视频
3. 视频生成完成后，OpenClaw 将视频文件发回给用户
4. 用户确认后，可继续选择发布到平台
```

**系统处理流程：**

```bash
# 调用脚本示例（必须使用 Python 3.12）
/opt/homebrew/bin/python3.12 scripts/generate_video.py \
  <image1> [image2] [image3] [image4] \
  --model=<模型 ID> \
  --duration=10 \
  --aspectRatio=16:9 \
  --token=<API 令牌>

# 下载生成的视频
/opt/homebrew/bin/python3.12 scripts/download_video.py <task-id> --token=<API 令牌>
```

**注意事项：**
- 最多支持 4 张图片生成 1 个视频
- 默认生成 10 秒视频，支持 16:9 或 9:16 比例
- 单个视频任务最多等待 30 分钟

### 3.2 平台登录管理

**用户操作流程：**

```
1. 用户请求检查平台登录状态
2. 系统检查对应平台登录态是否有效
3. 如失效，系统生成登录二维码并发送到微信
4. 用户微信扫码完成登录
5. 系统确认登录成功，保存登录态
```

**各平台端口与目录：**

| 平台 | 调试端口 | Cookie 目录 |
|------|---------|------------|
| 抖音 | 9224 | cookies/chrome_connect_dy |
| 小红书 | 9223 | cookies/chrome_connect_xhs |
| 快手 | 9225 | cookies/chrome_connect_ks |
| 视频号 | 9226 | cookies/chrome_connect_sph |

**登录检查命令：**

```bash
# 检查单个平台登录状态
/opt/homebrew/bin/python3.12 skills/auth/scripts/platform_login.py \
  --project-root ~/.openclaw/workspace/xiaolong-upload \
  --platform <platform> \
  --check-only

# 打开登录页（二维码模式）
/opt/homebrew/bin/python3.12 skills/auth/scripts/platform_login.py \
  --project-root ~/.openclaw/workspace/xiaolong-upload \
  --platform <platform> \
  --notify-wechat
```

### 3.3 视频发布功能

**用户操作流程：**

```
1. 用户发送视频文件或确认使用已生成的视频
2. 用户指定要发布的平台（可多选）
3. 系统检查各平台登录状态
4. 如登录有效，开始上传并发布
5. 发布完成后，回传发布结果（成功/失败原因）
```

**发布命令：**

```bash
# 单平台发布
/opt/homebrew/bin/python3.12 upload.py --platform <platform> <视频路径> "<标题>" "<文案>" "<标签 1, 标签 2>"

# 示例：发布到抖音
/opt/homebrew/bin/python3.12 upload.py -p douyin video.mp4 "记录生活" "美好的一天" "vlog,日常"

# 四平台顺序发布
/opt/homebrew/bin/python3.12 scripts/upload_xhs_ks_sph_generated.py <视频路径>
```

**各平台内容限制：**

| 平台 | 标题限制 | 标签限制 |
|------|---------|---------|
| 抖音 | ≤30 字 | - |
| 快手 | ≤15 字 | ≤4 个 |
| 小红书 | ≤20 字 | ≤5 个 |
| 视频号 | ≤64 字 | ≤10 个 |

---

## 🧹 四、文件管理与自动清理

### 4.1 文件目录

| 目录 | 用途 |
|------|------|
| `~/.openclaw/media/inbound/` | 接收用户发送的图片和视频 |
| `~/.openclaw/workspace/xiaolong-upload/flash_longxia/output/` | 生成的视频输出 |
| `~/.openclaw/workspace/xiaolong-upload/published/` | 已发布的视频备份 |

### 4.2 自动清理任务

**定时清理配置：**

```json
{
  "name": "video-cleanup-weekly",
  "schedule": {
    "expr": "0 1 * * 2",  // 每周二凌晨 1:00
    "tz": "Asia/Shanghai"
  },
  "payload": {
    "text": "cd ~/.openclaw/workspace/xiaolong-upload && /opt/homebrew/bin/python3.12 scripts/cleanup_uploaded_videos.py"
  }
}
```

**清理规则：**
- 清理目录：`flash_longxia/output/`
- 保留策略：保留最近 1 天的视频文件
- 触发时间：每周二凌晨 1:00 (Asia/Shanghai)

**手动清理命令：**

```bash
# 手动执行清理
/opt/homebrew/bin/python3.12 scripts/cleanup_uploaded_videos.py --manual

# 指定保留天数
/opt/homebrew/bin/python3.12 scripts/cleanup_uploaded_videos.py --manual --keep 7
```

---

## 📊 五、状态监控与故障排查

### 5.1 日志位置

| 日志类型 | 路径 |
|---------|------|
| 抖音上传日志 | `logs/douyin.log` |
| 快手上传日志 | `logs/kuaishou.log` |
| 小红书上传日志 | `logs/xiaohongshu.log` |
| 视频号上传日志 | `logs/shipinhao.log` |
| OpenClaw 系统日志 | `~/.openclaw/logs/` |

### 5.2 常见故障与处理

| 故障现象 | 可能原因 | 解决方案 |
|---------|---------|---------|
| 登录态失效 | Cookie 过期 | 重新扫码登录，运行 `platform_login.py --platform <平台>` |
| 上传失败 | 网络问题或平台限制 | 检查日志，确认视频格式和大小符合要求 |
| 生成视频超时 | API 队列拥堵 | 任务等待超过 30 分钟自动取消，可重新提交 |
| Chrome 连接失败 | 调试端口未启动 | 手动拉起 Chrome：`open -na "Google Chrome" --args --remote-debugging-port=<端口>` |

### 5.3 登录状态检查

```bash
# 每日自动检查（Cron 任务）
# 每天上午 10:10 执行
/opt/homebrew/bin/python3.12 skills/auth/scripts/scheduled_login_check.py
```

---

## 📋 六、客户说明指南

### 6.1 开始使用

**欢迎语模板：**

```
🦐 欢迎来到龙虾上传！

我是虾王，您的智能视频发布助手。我可以帮您：

📸 图生视频：发送 1-4 张图片，我帮您生成精美视频
🎬 多平台发布：支持抖音、快手、小红书、视频号一键发布
🔐 自动登录：登录失效时自动发送二维码，扫码即可

发送图片开始体验吧！
```

### 6.2 常用指令

| 用户指令 | 系统响应 |
|---------|---------|
| "发送图片" | 调用图生视频技能，生成视频后回传 |
| "检查登录" | 检查指定平台登录状态，失效则发送二维码 |
| "发布到抖音" | 将视频发布到抖音平台 |
| "全部发布" | 依次发布到四个平台 |
| "清理文件" | 手动执行文件清理任务 |

### 6.3 服务说明

**服务时间：**
- 自动服务：24 小时在线
- 人工支持：工作日 9:00-18:00

**处理时效：**
- 图生视频：5-15 分钟（取决于 API 队列）
- 视频上传：3-10 分钟/平台
- 登录验证：1-3 分钟

---

## 🔒 七、安全与隐私

### 7.1 数据安全

- 所有用户上传的图片/视频存储在本地
- 登录态信息加密存储于 `cookies/` 目录
- 定期清理机制防止磁盘占用过高

### 7.2 API 配置

编辑 `~/.openclaw/openclaw.json` 配置 API 密钥：

```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "sk-xxx",
    "ANTHROPIC_BASE_URL": "https://api.example.com",
    "ANTHROPIC_MODEL": "qwen3.5-plus"
  }
}
```

---

## 📞 八、支持与反馈

### 8.1 获取帮助

```bash
# 查看系统状态
openclaw --version

# 查看插件状态
openclaw plugins list

# 查看定时任务
openclaw cron list
```

### 8.2 问题反馈

提供以下信息以加快问题定位：

1. 故障发生时间
2. 涉及的 platform
3. 相关日志文件（`logs/` 目录下对应日志）
4. 错误截图

---

## 附录 A：命令速查表

### 技能命令

```bash
# 图生视频（必须使用 Python 3.12）
/opt/homebrew/bin/python3.12 scripts/generate_video.py <图片路径> --token=<令牌>
/opt/homebrew/bin/python3.12 scripts/download_video.py <任务 ID> --token=<令牌>

# 登录管理
/opt/homebrew/bin/python3.12 skills/auth/scripts/platform_login.py --platform <平台> --check-only
/opt/homebrew/bin/python3.12 skills/auth/scripts/platform_login.py --platform <平台> --notify-wechat

# 视频发布
/opt/homebrew/bin/python3.12 upload.py --platform <平台> <视频路径> "<标题>" "<文案>" "<标签>"

# 文件清理
/opt/homebrew/bin/python3.12 scripts/cleanup_uploaded_videos.py --manual --keep <天数>
```

### OpenClaw 命令

```bash
# 配置管理
openclaw config set <键> <值>
openclaw config get <键>

# 插件管理
openclaw plugins install <插件名>
openclaw plugins list

# Cron 管理
openclaw cron list
openclaw cron stop <任务 ID>
```

---

**文档结束**
