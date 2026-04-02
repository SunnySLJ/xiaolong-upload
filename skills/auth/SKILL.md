---
name: auth
description: 四平台登录技能。当用户提到“登录抖音/小红书/快手/视频号”“重新登录”“扫码登录”“登录失效”“会话过期”“先登录再发布”时必须使用。负责检查登录是否可复用、在需要时打开对应平台 connect Chrome、等待用户完成登录，并把登录态写入当前项目的 cookies/chrome_connect_* 目录。
---

# Auth Skill

本技能只负责登录验收和补登录，不负责实际发布。

## 目标

1. 上传前先判断目标平台登录是否还能复用。
2. 登录失效时打开对应平台的 connect Chrome，并把登录态写回当前项目正在使用的 `cookies/chrome_connect_*`。
3. 登录成功后停在“可发布”状态，等待后续上传动作。

## 当前项目

- 项目根目录默认使用当前仓库根目录：`/Users/mima0000/.openclaw/workspace/xiaolong-upload`
- 登录脚本：`skills/auth/scripts/platform_login.py`
- 权威流程说明：`docs/LOGIN_FLOW.md`
- 共享路径配置：`skills/runtime_config.json`

## 平台映射

- 抖音：`9224` + `cookies/chrome_connect_dy`
- 小红书：`9223` + `cookies/chrome_connect_xhs`
- 快手：`9225` + `cookies/chrome_connect_ks`
- 视频号：`9226` + `cookies/chrome_connect_sph`

## 当前稳定入口

脚本内部保留四平台逻辑，但当前命令行入口只开放 `shipinhao`。因此：

- 视频号登录检查/补登录可以直接走 `platform_login.py`
- 其它平台如需批量巡检，优先走 `login-monitor`
- 其它平台如需实际上传，优先走对应平台 connect 脚本或 `longxia-upload` 里的稳定入口

若项目目录或工作区变化，优先改：

- `skills/runtime_config.json`
- 环境变量 `XIAOLONG_UPLOAD_ROOT`

视频号登录检查：

```bash
/opt/homebrew/bin/python3.12 skills/auth/scripts/platform_login.py --project-root /Users/mima0000/.openclaw/workspace/xiaolong-upload --platform shipinhao --check-only
```

视频号检查后关闭浏览器：

```bash
/opt/homebrew/bin/python3.12 skills/auth/scripts/platform_login.py --project-root /Users/mima0000/.openclaw/workspace/xiaolong-upload --platform shipinhao --check-only --close-after-check
```

视频号打开登录并等待用户完成：

```bash
/opt/homebrew/bin/python3.12 skills/auth/scripts/platform_login.py --project-root /Users/mima0000/.openclaw/workspace/xiaolong-upload --platform shipinhao
```

视频号走二维码发微信模式：

```bash
/opt/homebrew/bin/python3.12 skills/auth/scripts/platform_login.py --project-root /Users/mima0000/.openclaw/workspace/xiaolong-upload --platform shipinhao --notify-wechat
```

## 执行规则

1. 一次只处理一个平台，不并行拉起多个登录窗口。
2. 凡是“先登录”“检查是否掉线”“登录后再决定发不发”，都先做登录检查，不自动跳到发布。
3. 若用户要求“检查完把浏览器关掉”，追加 `--close-after-check`。
4. 登录成功后的标准回传口径是“已登录，可发布，等待确认”，不是“已开始发布”。
5. `auth` 只负责把系统推进到“可发布”状态；真正发布统一交给根入口 `upload.py` 或平台 connect 上传脚本。
6. 若用户要求多个平台补登录，必须串行处理：一个平台验收完成后再进入下一个。

## 与上传流程的边界

仅登录、不发布时：

```bash
/opt/homebrew/bin/python3.12 upload.py --platform shipinhao "<video_path>" --login-only
```

说明：

- 当前根 CLI 公开平台只有 `shipinhao`
- 没有用户明确确认“开始发布”前，不执行真正上传

## 远程扫码场景

适用场景：用户不在电脑前，只能在微信里扫码。

1. 调用 `platform_login.py --notify-wechat`
2. 脚本会尝试打开登录页、切换到二维码登录、截图并等待登录完成
3. 登录是否完成以浏览器页面检测结果为准
4. 登录态仍写入当前项目的 `cookies/chrome_connect_*`

## 何时切到别的 skill

- 用户要巡检多个平台是否掉线：切到 `login-monitor`
- 用户要真正上传视频：切到 `longxia-upload`
