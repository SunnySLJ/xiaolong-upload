---
name: auth
description: 视频号登录技能。当用户提到“登录视频号”“重新登录视频号”“视频号扫码登录”“视频号登录失效”“视频号会话过期”“先登录视频号再发布”时必须使用。负责视频号 connect Chrome 的登录检查、打开登录页、等待用户完成登录，并保证最终登录信息写入与发布项目相同的 cookies/chrome_connect_sph 目录和端口。
---

# Auth Skill

本技能只负责登录，不直接负责发布。

目标：

1. 在上传前先检查平台当前登录是否还能复用。
2. 若不能复用，拉起该平台专用 connect Chrome 并提示用户登录。
3. 登录完成后，保持登录信息写入和发布项目完全一致的目录与端口，供后续上传直接复用。
4. 登录成功后默认停住，等待用户确认是否继续发布。
5. 当前只保留视频号登录入口，不再暴露其它平台入口。

## 当前项目根目录

- 项目根目录必须使用“当前机器上的真实仓库路径”。
- 优先使用环境变量 `OPENCLAW_UPLOAD_ROOT`；未设置时，再使用当前工作目录中的仓库路径。
- 禁止继续使用旧机器目录示例。

## Python 环境约束

- 优先使用仓库内 `.venv/bin/python3.12`。
- 若仓库内没有 `.venv/bin/python3.12`，再使用当前机器可用的 `python3.12`。
- 严禁继续依赖旧机器特有的固定解释器路径。

## 当前固定映射

- 视频号：`9226` + `cookies/chrome_connect_sph`

## 使用方式

强制约束：

1. 一次只允许处理一个平台。
2. 当前只允许处理视频号，不再接受其它平台。
3. 若用户没有明确指定平台，默认按视频号处理。

登录检查：

```bash
${OPENCLAW_PYTHON:-python3.12} skills/auth/scripts/platform_login.py --project-root "${OPENCLAW_UPLOAD_ROOT:-<repo-root>}" --platform shipinhao --check-only
```

若只是验收登录状态，且用户希望检查后自动关闭该平台浏览器：

```bash
${OPENCLAW_PYTHON:-python3.12} skills/auth/scripts/platform_login.py --project-root "${OPENCLAW_UPLOAD_ROOT:-<repo-root>}" --platform shipinhao --check-only --close-after-check
```

打开登录并等待用户完成：

```bash
${OPENCLAW_PYTHON:-python3.12} skills/auth/scripts/platform_login.py --project-root "${OPENCLAW_UPLOAD_ROOT:-<repo-root>}" --platform shipinhao
```

若用户不方便回到桌面电脑，可直接走“二维码发微信”模式：

```bash
${OPENCLAW_PYTHON:-python3.12} skills/auth/scripts/platform_login.py --project-root "${OPENCLAW_UPLOAD_ROOT:-<repo-root>}" --platform shipinhao --notify-wechat
```

## 必须遵守的规则

1. 登录信息会过期，上传前必须先做登录检查。
2. 若用户明确要求“检查完把浏览器关掉”，登录检查命令追加 `--close-after-check`。
3. 若登录不可复用，要明确提醒用户重新登录。
4. 登录 skill 只负责把登录态写入正确的 `cookies/chrome_connect_sph` 目录。
5. 登录完成后，继续调用原项目里的发布功能，不在 auth skill 内重复实现上传逻辑。
6. 若用户明确要求“登录后还要再确认再发布”，auth skill 在检测到已登录后必须停住，并回传“已登录，可发布，等待确认”。
7. 真正发布时只允许调用统一发布接口 `upload.py`，不在 auth skill 内拼平台私有调用。
8. 当前 skill 不处理其它平台；若用户提到其它平台，必须明确说明入口已关闭。
9. 若用户无法连接桌面电脑，auth skill 应优先走：
   - 打开上传平台网页
   - 切到二维码登录
   - 截图当前二维码
   - 交给 OpenClaw 发送到微信
   - 持续轮询页面直到检测到已登录
   - 登录成功后，把控制权交还给发布流程继续上传

## 发布接口约束

若只是“登录检查/补登录”，而不是立刻发布，优先使用：

```bash
${OPENCLAW_PYTHON:-python3.12} upload.py --platform <platform> <video_path> --login-only
```

说明：

- `upload.py` 默认行为是“登录成功后继续发布”
- 只有显式传 `--login-only`，才会在登录成功后停住，不继续发布

登录完成后的发布统一走：

```bash
${OPENCLAW_PYTHON:-python3.12} upload.py --platform <platform> <video_path> <title> <description> <tags>
```

或：

```python
from upload import upload
```

`auth` 不直接调用平台内部上传模块；只负责把系统推进到“可发布”状态。

## 远程登录流程

适用场景：用户无法直接操作桌面电脑，只能在微信里完成扫码登录。

1. 调用：

```bash
${OPENCLAW_PYTHON:-python3.12} skills/auth/scripts/platform_login.py --project-root "${OPENCLAW_UPLOAD_ROOT:-<repo-root>}" --platform shipinhao --notify-wechat
```

同一时刻只允许处理视频号，不要并发启动其他平台登录流程。

2. 脚本会：
   - 拉起该平台专用 connect Chrome
   - 尝试切到二维码登录页
   - 截图当前登录页
   - 通过 OpenClaw 的 `openclaw-weixin` 通道把截图发到微信
   - 继续轮询浏览器页面，直到检测到已登录

3. 登录成功后：
   - 登录信息仍写入当前项目正在使用的 `cookies/chrome_connect_sph`
   - 后续直接继续调用原来的发布功能

说明：

- 当前环境里稳定可用的是“脚本生成二维码/截图 + OpenClaw 发送到微信 + 页面轮询登录成功”。
- “等待微信里回复一条登录成功消息”可以作为用户交互提示，但真正的继续条件仍以浏览器页面检测到已登录为准。

## 给其他项目复用

`skills/auth/scripts/platform_login.py` 是单文件脚本，可以复制到其他项目中使用。

要求：

1. 其他项目调用时传自己的 `--project-root`。
2. 若想复用当前项目已有登录信息，必须沿用视频号这一组端口和 `cookies/chrome_connect_sph` 目录。
3. 登录完成后，其他项目再拿这套登录信息继续上传。
