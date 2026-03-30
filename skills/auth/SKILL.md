---
name: auth
description: 四平台登录技能。当用户提到“登录抖音/小红书/快手/视频号”“重新登录”“扫码登录”“登录失效”“会话过期”“先登录再发布”时必须使用。负责四个平台 connect Chrome 的登录检查、打开登录页、等待用户完成登录，并保证最终登录信息写入与发布项目相同的 cookies/chrome_connect_* 目录和端口。
---

# Auth Skill

本技能只负责登录，不直接负责发布。

目标：

1. 在上传前先检查平台当前登录是否还能复用。
2. 若不能复用，拉起该平台专用 connect Chrome 并提示用户登录。
3. 登录完成后，保持登录信息写入和发布项目完全一致的目录与端口，供后续上传直接复用。
4. 登录成功后默认停住，等待用户确认是否继续发布。
5. 单次只处理一个平台的登录，不并行拉起多个平台登录窗口。

## 当前项目根目录

- 当前本机项目根目录：`/Users/h/Desktop/xiaolong-upload`
- 若后续把仓库同步到 OpenClaw 工作区，再把命令里的 `--project-root` 替换成真实副本路径；禁止继续使用旧机器目录。

## 四个平台固定映射

- 抖音：`9224` + `cookies/chrome_connect_dy`
- 小红书：`9223` + `cookies/chrome_connect_xhs`
- 快手：`9225` + `cookies/chrome_connect_ks`
- 视频号：`9226` + `cookies/chrome_connect_sph`

## 使用方式

强制约束：

1. 一次只允许处理一个平台。
2. 若用户要登录多个平台，必须串行执行：完成一个平台的登录验收后，再开始下一个。
3. 若用户没有明确指定平台，先追问平台名，不得自行同时打开多个平台登录页。

登录检查：

```bash
python skills/auth/scripts/platform_login.py --project-root /Users/h/Desktop/xiaolong-upload --platform douyin --check-only
```

若只是验收登录状态，且用户希望检查后自动关闭该平台浏览器：

```bash
python skills/auth/scripts/platform_login.py --project-root /Users/h/Desktop/xiaolong-upload --platform douyin --check-only --close-after-check
```

打开登录并等待用户完成：

```bash
python skills/auth/scripts/platform_login.py --project-root /Users/h/Desktop/xiaolong-upload --platform shipinhao
```

若用户不方便回到桌面电脑，可直接走“二维码发微信”模式：

```bash
python skills/auth/scripts/platform_login.py --project-root /Users/h/Desktop/xiaolong-upload --platform kuaishou --notify-wechat
```

## 必须遵守的规则

1. 登录信息会过期，上传前必须先做登录检查。
2. 若用户明确要求“检查完把浏览器关掉”，登录检查命令追加 `--close-after-check`。
3. 若登录不可复用，要明确提醒用户重新登录。
4. 登录 skill 只负责把登录态写入正确的 `cookies/chrome_connect_*` 目录。
5. 登录完成后，继续调用原项目里的发布功能，不在 auth skill 内重复实现上传逻辑。
6. 若用户明确要求“登录后还要再确认再发布”，auth skill 在检测到已登录后必须停住，并回传“已登录，可发布，等待确认”。
7. 真正发布时只允许调用统一发布接口 `upload.py`，不在 auth skill 内拼平台私有调用。
8. 若批量任务里某个平台登录失败，应明确标记该平台跳过，而不是阻塞其他平台。
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
python upload.py --platform <platform> <video_path> --login-only
```

说明：

- `upload.py` 默认行为是“登录成功后继续发布”
- 只有显式传 `--login-only`，才会在登录成功后停住，不继续发布

登录完成后的发布统一走：

```bash
python upload.py --platform <platform> <video_path> <title> <description> <tags>
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
python skills/auth/scripts/platform_login.py --project-root /Users/h/Desktop/xiaolong-upload --platform <platform> --notify-wechat
```

同一时刻只允许处理这一个 `<platform>`，不要并发启动其他平台登录流程。

2. 脚本会：
   - 拉起该平台专用 connect Chrome
   - 尝试切到二维码登录页
   - 截图当前登录页
   - 通过 OpenClaw 的 `openclaw-weixin` 通道把截图发到微信
   - 继续轮询浏览器页面，直到检测到已登录

3. 登录成功后：
   - 登录信息仍写入当前项目正在使用的 `cookies/chrome_connect_*`
   - 后续直接继续调用原来的发布功能

说明：

- 当前环境里稳定可用的是“脚本生成二维码/截图 + OpenClaw 发送到微信 + 页面轮询登录成功”。
- “等待微信里回复一条登录成功消息”可以作为用户交互提示，但真正的继续条件仍以浏览器页面检测到已登录为准。

## 给其他项目复用

`skills/auth/scripts/platform_login.py` 是单文件脚本，可以复制到其他项目中使用。

要求：

1. 其他项目调用时传自己的 `--project-root`。
2. 若想复用当前项目已有登录信息，必须沿用同一组端口和 `cookies/chrome_connect_*` 目录。
3. 登录完成后，其他项目再拿这套登录信息继续上传。
