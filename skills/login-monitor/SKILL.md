---
name: login-monitor
description: 四平台登录状态巡检技能。当用户提到“定时检查登录状态”“巡检哪些平台掉线了”“批量检查抖音/小红书/快手/视频号登录是否失效”“提醒重新登录”“定时发二维码重登”时必须使用。负责独立巡检四个平台 connect Chrome 的登录有效性，并在失效时触发重新登录。
---

# Login Monitor Skill

本技能负责四平台登录巡检，不直接发布视频。

## 入口

- 巡检脚本：`skills/login-monitor/scripts/login_status_monitor.py`
- 依赖登录脚本：`skills/auth/scripts/platform_login.py`
- 默认项目根目录：当前仓库根目录
- 结果输出：`logs/login_monitor/latest.json`
- 共享路径配置：`skills/runtime_config.json`

## 能力

- 单次检查四个平台或指定平台
- 轮询检查
- 登录失效时触发补登录
- 可选触发二维码发微信
- 将巡检结果写入 JSON

## 标准命令

检查全部平台：

```bash
/opt/homebrew/bin/python3.12 skills/login-monitor/scripts/login_status_monitor.py
```

只检查视频号和快手：

```bash
/opt/homebrew/bin/python3.12 skills/login-monitor/scripts/login_status_monitor.py --platform shipinhao --platform kuaishou
```

发现失效后自动打开登录页：

```bash
/opt/homebrew/bin/python3.12 skills/login-monitor/scripts/login_status_monitor.py --trigger-relogin
```

发现失效后自动走二维码发微信：

```bash
/opt/homebrew/bin/python3.12 skills/login-monitor/scripts/login_status_monitor.py --trigger-relogin --notify-wechat
```

每 10 分钟巡检一次，共 12 轮：

```bash
/opt/homebrew/bin/python3.12 skills/login-monitor/scripts/login_status_monitor.py --interval 600 --max-rounds 12
```

## 输出约定

终端输出会包含：

- 每个平台是否有效
- 失效原因
- 是否已触发重新登录

JSON 重点字段：

- `all_valid`
- `expired_platforms`
- `results[].platform`
- `results[].status`
- `results[].message`
- `results[].relogin_message`

## 执行规则

1. 巡检只判断登录是否可复用，不承诺上传一定成功。
2. 若用户要求“只报告，不动作”，不要加 `--trigger-relogin`。
3. 若用户要求“掉线就直接叫我扫码”，使用 `--trigger-relogin --notify-wechat`。
4. 长期定时任务优先交给外部调度器；脚本默认设计为单次执行。
5. 若用户下一步要求“现在把掉线的平台重新登录”，切回 `auth` skill 串行处理。
