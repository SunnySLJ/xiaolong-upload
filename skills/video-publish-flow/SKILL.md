---
name: video-publish-flow
description: Complete video publish workflow: receive images → generate video via zhenlongxia → poll every 30s using download_latest_video.py → auto-upload to 4 platforms (Douyin, Xiaohongshu, Kuaishou, Video Account). Polls up to 30min. Moves files to upload_back after completion. Reuses browser session across platforms.
---

# 视频发布完整流程

当用户发送图片（1-5 张）时，自动执行完整视频发布流程。

## 触发条件

- 用户发送 1-5 张图片
- 用户说"发视频"、"做视频"、"上传视频"等

## 完整流程

### 1️⃣ 接收图片

- 保存用户发送的图片到临时目录
- 通知用户：收到图片，开始生成视频

### 2️⃣ 生成视频（帧龙虾）

**步骤 2.1 - 发起生成任务：**
```bash
cd ~/.openclaw/workspace/openclaw_upload/flash_longxia
.venv/bin/python zhenlongxia_workflow.py <图片路径>
```
- 从输出中提取 **任务 ID**（如：任务 ID: 1364）
- 记录任务 ID 用于后续轮询

**步骤 2.2 - 轮询下载视频：**
```bash
cd ~/.openclaw/workspace/openclaw_upload/flash_longxia
.venv/bin/python download_latest_video.py <任务 ID>
```

**轮询策略：**
- 每 **30 秒** 调用一次 `download_latest_video.py`
- 最多等待 **30 分钟**（1800 秒）
- 如果脚本成功下载视频（输出"已保存"），继续下一步
- 如果超时（30 分钟仍未生成），放弃并通知用户

**Token 位置：** `~/.openclaw/workspace/openclaw_upload/flash_longxia/token.txt`

### 3️⃣ 生成文案

根据视频内容自动生成：
- **标题：** ≤30 字（抖音/快手≤15 字，小红书≤20 字，视频号≤64 字）
- **文案：** 描述性文字
- **标签：** 3-5 个话题标签

### 4️⃣ 上传 4 个平台

**统一命令格式：**
```bash
cd ~/.openclaw/workspace/xiaolong-upload
.venv313/bin/python upload.py -p <平台> <视频路径> "<标题>" "<文案>" "<标签>"
```

**上传顺序：**
1. 抖音 (douyin)
2. 小红书 (xiaohongshu)
3. 快手 (kuaishou)
4. 视频号 (shipinhao)

**浏览器管理：**
- 每个平台上传完成后**必须关闭浏览器**
- 下一个平台重新打开一个新的浏览器窗口
- 登录态通过 cookies 复用，不需要保持浏览器打开
- 确保不会有浏览器堆积

**实现方式：**
- 上传命令**不设置** `DOUYIN_DETACH_BROWSER` 环境变量
- 让脚本自动管理浏览器生命周期（上传完成自动关闭）
- 每个平台独立打开/关闭浏览器

**注意：** 小红书上传时会打开系统文件选择对话框，脚本会自动尝试关闭（ESC + Cmd+W）。

**登录通知：**
- 所有平台（抖音、小红书、快手、视频号）登录失效时 → 自动发送微信通知
- 通知内容包含平台名称和登录指引
- 视频号通知包含直接登录链接

### 5️⃣ 迁移文件

**上传完成后，将文件移动到备份目录：**
```bash
# 创建备份目录（如果不存在）
mkdir -p ~/Desktop/upload_back

# 移动视频
mv ~/Desktop/video_upload/generated_video.mp4 ~/Desktop/upload_back/

# 移动原始图片
mv /Users/mima0000/.openclaw/media/inbound/<图片文件名>.jpg ~/Desktop/upload_back/
```

**备份目录：** `~/Desktop/upload_back/`

### 6️⃣ 通知用户

**每个平台发布成功后通知：**
- "✅ 抖音发布成功！"
- "✅ 小红书发布成功！"
- "✅ 快手发布成功！"
- "✅ 视频号发布成功！"

**文件迁移后通知：**
- "📁 文件已备份到 ~/Desktop/upload_back/"

**全部完成后汇总通知：**
```
🎊 4 个平台全部发布成功！

| 平台 | 状态 |
|------|------|
| ✅ 抖音 | 发布成功 |
| ✅ 小红书 | 发布成功 |
| ✅ 快手 | 发布成功 |
| ✅ 视频号 | 发布成功 |

文案：
- 标题：xxx
- 文案：xxx
- 标签：xxx

📁 文件已备份：~/Desktop/upload_back/
```

## 项目路径

| 项目 | 路径 |
|------|------|
| 视频生成 | `~/.openclaw/workspace/openclaw_upload/` |
| 视频上传 | `~/.openclaw/workspace/xiaolong-upload/` |
| 视频输出 | `~/Desktop/video_upload/` |
| 文件备份 | `~/Desktop/upload_back/` |

## Python 环境

- 视频生成：`~/.openclaw/workspace/openclaw_upload/flash_longxia/.venv/bin/python`
- 视频上传：`~/.openclaw/workspace/xiaolong-upload/.venv313/bin/python`

## 平台限制

| 平台 | 标题限制 | 标签限制 |
|------|----------|----------|
| 抖音 | ≤30 字 | - |
| 快手 | ≤15 字 | ≤4 |
| 视频号 | ≤64 字 | ≤10 |
| 小红书 | ≤20 字 | ≤5 |

## 错误处理

### 视频生成失败
- Token 无效 → 提示用户检查 token
- 网络错误 → 重试 3 次
- 超时 → 30 分钟后放弃，通知用户

### 平台上传失败
- 未登录 → 打开浏览器引导扫码
- 页面结构变化 → 记录错误，跳过该平台
- 网络错误 → 重试 2 次

## 示例触发

用户发送图片 → 自动执行：
```
📸 收到图片，开始生成视频...
🎬 发起视频生成任务... (任务 ID: 1364)
🎬 视频生成中... (每 30 秒轮询一次)
✅ 视频下载完成！
✍️ 文案已生成
📤 开始上传抖音...
✅ 抖音发布成功！
📤 开始上传小红书...
✅ 小红书发布成功！
📤 开始上传快手...
✅ 快手发布成功！
📤 开始上传视频号...
✅ 视频号发布成功！
📁 文件已备份到 ~/Desktop/upload_back/
🎊 4 个平台全部发布成功！
```

## 配置项

```bash
# 帧龙虾 Token
TOKEN_FILE=~/Desktop/shuang/openclaw_upload/flash_longxia/token.txt

# 视频输出目录
VIDEO_OUTPUT_DIR=~/Desktop/video_upload/

# 文件备份目录
BACKUP_DIR=~/Desktop/upload_back/

# 轮询配置
POLL_INTERVAL=30  # 秒
MAX_WAIT_MINUTES=30  # 分钟

# 浏览器配置
DOUYIN_DETACH_BROWSER=1  # 复用浏览器
```

## 注意事项

1. **首次使用需登录**：4 个平台首次上传会打开浏览器引导扫码登录，登录态保存在 cookies 目录
2. **Token 有效期**：帧龙虾 Token 需保持有效，失效需更新
3. **浏览器复用**：上传流程中浏览器保持打开，全部完成后关闭
4. **文案适配**：根据不同平台限制自动调整标题长度
5. **文件备份**：上传完成后自动迁移到 `~/Desktop/upload_back/`
