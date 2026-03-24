---
name: longxia-upload
description: 龙虾上传技能。当用户提到“上传到抖音/小红书/快手/视频号”“多平台发布”“继续上传”“重传”“cookie 登录/导入 cookie/导出 cookie”时必须使用。基于 Windows connect 模式（9223/9224/9225/9226）执行四平台自动上传、cookie 导入校验、cookie 导出复用；默认优先使用项目内 PowerShell 脚本并回传明确发布结果（成功/失败原因）。
---

# 龙虾上传 (Longxia Upload) Skill

本技能用于在 Windows 环境下，将本地视频自动化上传到抖音、小红书、快手、视频号创作者平台，并支持 cookie 导入/导出复用登录态。

## 项目路径

- **项目根目录**：`C:\Users\爽爽\Desktop\shuang\xiaolong-upload`
- **技能目录**：`C:\Users\爽爽\.claude\skills\longxia-upload\`

## 支持平台

| 平台 | 上传脚本 | 导出 cookie 脚本 | 端口 |
|------|----------|-------------------|------|
| 抖音 | `scripts/upload_douyin_connect.ps1` | `scripts/export_douyin_cookie.ps1` | 9224 |
| 小红书 | `scripts/upload_xiaohongshu_connect.ps1` | `scripts/export_xiaohongshu_cookie.ps1` | 9223 |
| 快手 | `scripts/upload_kuaishou_connect.ps1` | `scripts/export_kuaishou_cookie.ps1` | 9225 |
| 视频号 | `scripts/upload_shipinhao_connect.ps1` | `scripts/export_shipinhao_cookie.ps1` | 9226 |

## 标准执行流程

### 1) 单平台上传（默认）

在项目根目录执行（推荐）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\upload_douyin_connect.ps1" "C:\Users\爽爽\Desktop\2.mp4" "今日份生活小记录" "文案" "标签1,标签2"
```

其他平台同理替换脚本名。

### 2) 四平台顺序上传（抖音优先）

```powershell
python scripts/upload_xhs_ks_sph_generated.py "C:\Users\爽爽\Desktop\2.mp4"
```

### 3) cookie 导入后上传（推荐给“拿到 cookie 不想扫码”的场景）

先校验 cookie：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\import_cookie_and_upload.ps1" -Platform douyin -CookieFile "C:\path\dy_cookie.json" -ValidateOnly
```

校验通过后上传：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\import_cookie_and_upload.ps1" -Platform douyin -CookieFile "C:\path\dy_cookie.json" -VideoPath "C:\Users\爽爽\Desktop\2.mp4" -Title "今日份生活小记录" -Description "文案" -Tags "生活记录,日常分享"
```

### 4) cookie 导出（拿不到 cookie 时）

```powershell
# 抖音
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\export_douyin_cookie.ps1"
# 小红书
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\export_xiaohongshu_cookie.ps1"
# 快手
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\export_kuaishou_cookie.ps1"
# 视频号
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\export_shipinhao_cookie.ps1"
```

## 执行原则（必须遵守）

1. **先确认目标平台与视频路径**，再执行脚本。
2. **每次回传结果必须包含**：
   - 是否发布成功
   - 关键日志节点（进入发布页/上传完毕/发布成功）
   - 最终退出码
3. 出现“卡住”时，不做模糊判断，优先读终端日志文件确认真实状态。
4. 若用户说“页面没打开/没反应”，先检查对应端口是否监听，再重启该平台调试 Chrome。
5. 不擅自删用户业务文件；清理仅限缓存或用户明确要求删除的项。

## 环境要求

- Python 3.10+
- Google Chrome
- 依赖：`pip install -r requirements.txt`

## 常见故障与处理

1. `COOKIE_COUNT: 0`
   - 多数是登录发生在非目标调试窗口；重启目标端口浏览器后重新登录再导出。
2. `COOKIE_NOT_VALID`
   - 先跑 `-ValidateOnly`，若失败再让用户在对应端口窗口重新登录。
3. `ConnectionRefusedError / WinError 1225`
   - 端口进程丢失或浏览器被关；先重启对应端口 Chrome 再重试。
4. Shell 报 `Aborted`
   - 常见于等待命令而非主任务失败；以主任务日志 `exit_code` 为准。
