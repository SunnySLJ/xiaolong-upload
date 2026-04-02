---
name: longxia-upload
description: 龙虾上传技能。当用户提到“上传到抖音/小红书/快手/视频号”“多平台发布”“继续上传”“重传”“cookie 登录/导入 cookie/导出 cookie”时必须使用。覆盖当前仓库中的统一上传入口、Windows connect 脚本和登录前置检查，并要求明确回传成功或失败原因。
---

# Longxia Upload Skill

本技能负责把本地视频发布到创作者平台，并在需要时衔接登录检查、重传排障和 cookie 导入导出。

## 当前仓库里的稳定入口

- 统一 Python 入口：`upload.py`
- Windows connect 上传脚本：
  - `scripts/upload_douyin_connect.ps1`
  - `scripts/upload_xiaohongshu_connect.ps1`
  - `scripts/upload_kuaishou_connect.ps1`
  - `scripts/upload_shipinhao_connect.ps1`
- 登录检查脚本：`skills/auth/scripts/platform_login.py`
- 权威流程：`docs/LOGIN_FLOW.md`

## 重要现状

当前仓库里“平台实现”仍包含四个平台，但公开 CLI 有限制：

- `upload.py` 当前命令行只开放 `shipinhao`
- 抖音 / 小红书 / 快手的稳定命令仍以 Windows connect 脚本为主
- 不要再宣称 `upload.py --platform douyin|xiaohongshu|kuaishou` 是当前稳定 CLI

## 执行原则

1. 先确认目标平台和视频路径，再执行上传。
2. 上传前必须先判断登录是否还能复用。
3. 用户只说“先看看登录”“先补登录”时，只做登录，不自动开始发布。
4. 用户要求“登录后还要确认再发布”时，登录成功后停住。
5. 批量任务里某个平台登录失效时，标记跳过，不阻塞其他平台。
6. 每次回传结果必须说明：是否成功、关键日志节点、失败原因或跳过原因。
7. 若日志只有“已点击发布”但没有最终成功信号，不能算成功。

## 视频号：当前统一 CLI

登录检查但不发布：

```bash
/opt/homebrew/bin/python3.12 upload.py --platform shipinhao "<video_path>" --login-only
```

直接发布视频号：

```bash
/opt/homebrew/bin/python3.12 upload.py --platform shipinhao "<video_path>" "<title>" "<description>" "<tag1,tag2>"
```

说明：

- `upload.py` 发布成功后会尝试自动关闭该平台 connect Chrome
- `--login-only` 用于“先验收登录，再等用户确认”

## 四平台 connect 入口

抖音：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\upload_douyin_connect.ps1" "<video_path>" "<title>" "<description>" "<tags>"
```

小红书：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\upload_xiaohongshu_connect.ps1" "<video_path>" "<title>" "<description>" "<tags>"
```

快手：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\upload_kuaishou_connect.ps1" "<video_path>" "<title>" "<description>" "<tags>"
```

视频号：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\upload_shipinhao_connect.ps1" "<video_path>" "<title>" "<description>" "<tags>"
```

## Cookie 相关

导入 cookie 后校验：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\import_cookie_and_upload.ps1" -Platform douyin -CookieFile "C:\path\cookie.json" -ValidateOnly
```

导入 cookie 后上传：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\import_cookie_and_upload.ps1" -Platform douyin -CookieFile "C:\path\cookie.json" -VideoPath "<video_path>" -Title "<title>" -Description "<description>" -Tags "<tags>"
```

导出 cookie：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\export_douyin_cookie.ps1"
```

其它平台同理替换脚本名。

## 重传和排障

遇到“像是没发出去”“页面卡住了”“再发一次”时：

1. 先读对应平台日志，不凭浏览器表象判断。
2. 快手优先看 `logs/kuaishou.log`，抖音看 `logs/douyin.log`，小红书看 `logs/xiaohongshu.log`，视频号看 `logs/shipinhao.log`。
3. 若登录失效，先切回 `auth` 补登录，再决定是否重传。
4. 成功判定以日志出现明确成功信号为准，不以“点过发布按钮”代替成功。

## 与 auth 的边界

- `auth` 负责登录验收和补登录
- `longxia-upload` 负责真正发布和结果汇总

若用户先说“先登录再等我确认”，先走 `auth`，不要直接执行上传。
