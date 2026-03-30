---
name: login-monitor
description: 四平台登录状态巡检技能。当用户提到“定时检查登录状态”“巡检哪些平台掉线了”“批量检查抖音/小红书/快手/视频号登录是否失效”“提醒重新登录”“定时发二维码重登”时必须使用。负责独立巡检四个平台 connect Chrome 的登录有效性，并在失效时输出失效平台、触发重新登录、可选发送二维码到微信。
---

# Login Monitor Skill

本技能只负责“巡检登录状态”和“触发重新登录”，不直接发布视频。

适用场景：

1. 用户想定时检查四个平台哪些已经掉登录。
2. 用户想批量知道哪些平台需要重新扫码。
3. 用户想在失效时自动打开登录页。
4. 用户不在电脑前，想把登录二维码发到微信。

## 项目路径

- 项目根目录：`/Users/mima0000/.openclaw/workspace/xiaolong-upload`
- 巡检脚本：`skills/login-monitor/scripts/login_status_monitor.py`
- 依赖登录 skill：`skills/auth/scripts/platform_login.py`

## 巡检能力

- 批量检查：抖音 / 小红书 / 快手 / 视频号
- 单次检查
- 轮询检查（适合定时任务）
- 发现失效后自动拉起重新登录
- 可选把二维码发到微信
- 结果落盘到 `logs/login_monitor/latest.json`

## 标准用法

单次检查全部平台：

```bash
python skills/login-monitor/scripts/login_status_monitor.py
```

只检查视频号和快手：

```bash
python skills/login-monitor/scripts/login_status_monitor.py --platform shipinhao --platform kuaishou
```

发现失效后自动打开登录页：

```bash
python skills/login-monitor/scripts/login_status_monitor.py --trigger-relogin
```

发现失效后自动发微信二维码：

```bash
python skills/login-monitor/scripts/login_status_monitor.py --trigger-relogin --notify-wechat
```

每 10 分钟巡检一次，共执行 12 轮：

```bash
python skills/login-monitor/scripts/login_status_monitor.py --interval 600 --max-rounds 12
```

## 定时任务建议

适合外部调度器调用，例如 `cron` / `launchd` / OpenClaw 的定时能力。

示例：

```bash
*/10 * * * * cd /Users/mima0000/.openclaw/workspace/xiaolong-upload && /usr/bin/python3 skills/login-monitor/scripts/login_status_monitor.py --trigger-relogin --notify-wechat
```

## 输出约定

终端输出：

- 每个平台是否有效
- 失效原因
- 是否已触发重新登录

JSON 文件：

- `logs/login_monitor/latest.json`
- `logs/login_monitor/status_YYYYMMDD_HHMMSS.json`

字段重点：

- `all_valid`
- `expired_platforms`
- `results[].platform`
- `results[].status`
- `results[].message`
- `results[].relogin_message`

## 执行原则

1. 巡检只判断“当前登录是否可复用”，不判断上传是否一定成功。
2. 发现失效时，优先复用 `auth` skill 的登录逻辑，不重新发明平台判断标准。
3. 若用户要求“只报告，不动作”，不要加 `--trigger-relogin`。
4. 若用户要求“发现失效直接通知我扫码”，使用 `--trigger-relogin --notify-wechat`。
5. 若是长期定时任务，优先让脚本单次执行，由外部调度器控制周期；不要默认常驻。

## 与 auth skill 的关系

- `login-monitor` 负责巡检和触发
- `auth` 负责真正打开登录页、发二维码、等待用户扫码

如果用户接下来要求“现在就帮我把失效的平台重新登录”，继续使用 `auth` skill。
