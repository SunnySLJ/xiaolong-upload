# flash-video-workflow SKILL

## 描述
完整的图片生成视频并发布到多平台的工作流技能。包括图片接收、参数确认、视频生成、轮询查询、发布确认、多平台上传。

## 触发条件
- 用户发送图片后说"生成视频"、"图生视频"、"图片转视频"等关键字
- 或用户明确说要走完整流程

## 执行流程

### 阶段 1: 接收图片并确认参数
1. 保存图片到 `inbound_images/` 目录
2. 向用户展示默认参数并询问是否修改：
   - `model`: auto
   - `aspectRatio`: 9:16
   - `duration`: 10（秒）
3. **必须等待用户明确说"确定生成"、"确认生成"、"开始生成"等才继续**

### 阶段 2: 调用视频生成接口
1. 执行命令生成视频：
```bash
cd /Users/mima0000/.openclaw/workspace/openclaw_upload/flash_longxia
python3 zhenlongxia_workflow.py "<图片路径>" --model=auto --aspectRatio=9:16 --duration=10
```
2. 获取任务 ID，记录到 `pending_tasks.json`

### 阶段 3: 后台轮询查询
1. 启动后台轮询脚本（不阻塞主会话）
2. 每 30 秒查询一次任务状态
3. 最多轮询 30 分钟（60 次）
4. 查询到视频完成后：
   - 下载视频到 `flash_longxia/output/<任务 ID>.mp4`
   - 终止轮询脚本
   - 通知用户视频已完成

### 阶段 4: 确认发布
1. 将生成的视频发送给用户微信
2. 询问用户：
   - 是否确认发布
   - 发布到哪些平台（抖音/快手/小红书/视频号/全部）
3. **必须等待用户明确说"确认发布"、"可以发布"、"发布"等才继续**

### 阶段 5: 多平台上传
1. 检查各平台登录状态
2. 如有平台未登录，调用 auth 技能获取二维码
3. 按顺序上传到指定平台：
```bash
cd /Users/mima0000/.openclaw/workspace/xiaolong-upload
/opt/homebrew/bin/python3.12 upload.py -p <平台> "<视频路径>" "<标题>" "<文案>" "<标签>"
```
4. 汇总发布结果通知用户

## 文件结构
```
/Users/mima0000/.openclaw/workspace/
├── inbound_images/              # 保存接收的图片
├── openclaw_upload/
│   ├── flash_longxia/
│   │   ├── output/              # 生成的视频
│   │   └── pending_tasks.json   # 待处理任务记录
│   └── cookies/                 # 平台登录 cookies
└── xiaolong-upload/
    ├── upload.py                # 上传脚本
    ├── skills/auth/scripts/
    │   └── platform_login.py    # 登录脚本
    └── logs/auth_qr/            # 登录二维码
```

## 重要规则
- ⚠️ **生成视频前必须用户确认**
- ⚠️ **发布视频前必须用户确认**
- ⚠️ **每次只能调用一次 workflow，调用前检查 output 目录**
- ⚠️ **轮询在后台运行，不阻塞主会话**
- ⚠️ **单个视频超时 30 分钟则放弃，并必须通知用户任务失败**

## ⚠️ 超时处理硬性规定
- **单个视频任务最多等待 30 分钟（从提交任务开始计时）**
- **超时后必须放弃任务，停止轮询**
- **超时后必须通知用户任务失败，说明原因**
- 通知内容需包含：任务 ID、开始时间、超时时间、最终状态、失败原因
- 询问用户是否需要重新生成该任务

## ⚠️ 轮询方式硬性规定
- ❌ **禁止**通过监控 output 目录是否有视频文件来判断生成完成
- ✅ **必须**使用 API 接口（`/api/v1/aiMediaGenerations/getById`）每 30 秒查询任务状态
- ✅ 查询到状态=2（已完成）后，主动下载视频到本地
- ✅ 下载完成后，**必须**主动发送微信通知用户，附带视频文件
- ✅ 使用通用轮询脚本模板：`poll_task_template.py`

## 默认发布信息
- **标题**: 可爱日常 ✨
- **文案**: 元气满满的日常记录～ 每一天都值得被记录 📸💕
- **标签**: 可爱，日常，生活记录

## 相关技能
- `flash-longxia`: 图片生成视频
- `longxia-upload`: 多平台上传
- `auth`: 平台登录
