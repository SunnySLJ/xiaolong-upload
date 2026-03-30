# Claude Init

本文件定义 Claude 在本项目中的默认执行规范。

## 项目目标

本项目用于把本地视频发布到四个平台：

- 抖音
- 小红书
- 快手
- 视频号

## 核心职责拆分

### 1. auth 负责登录

`auth` 只负责：

- 检查登录是否可复用
- 打开登录页
- 获取二维码原图
- 等待用户完成登录
- 把登录信息写入对应 `cookies/chrome_connect_*`

`auth` 不负责自动发布。

### 2. upload 负责发布

真正发布统一走：

```bash
python upload.py --platform <platform> <video_path> [title] [description] [tags]
```

或：

```python
from upload import upload
```

不直接在外层调用平台内部上传模块。

## 登录后发布规则

1. 登录完成后默认停住，不自动发布。
2. 若用户要求“登录后还要确认再发布”，必须回传：
   - 已登录
   - 可发布
   - 等待确认
3. 只有在用户明确确认后，才调用 `upload.py` 进入发布阶段。

## 二维码与微信规则

1. 登录脚本负责生成二维码原图。
2. 若需要把二维码发送到微信，发送动作由 OpenClaw 执行。
3. 脚本不承担“自己发微信”的职责；脚本只负责：
   - 产出二维码文件
   - 调用 OpenClaw 所需参数
   - 轮询浏览器页面判断是否已登录

## 四平台端口与目录

- 抖音：`9224` + `cookies/chrome_connect_dy`
- 小红书：`9223` + `cookies/chrome_connect_xhs`
- 快手：`9225` + `cookies/chrome_connect_ks`
- 视频号：`9226` + `cookies/chrome_connect_sph`

## 统一执行口径

1. 上传前先检查登录。
2. 登录失效先走 auth。
3. 登录成功后等待用户确认。
4. 用户确认后再调用统一发布接口。
5. 发布结果必须按日志判断，不由页面表象推断。
