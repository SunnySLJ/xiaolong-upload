---
name: longxia-bootstrap
description: Bootstrap 技能。当用户提到“初始化项目”“配置项目根目录”“配置 Python 3.12”“检查环境”“安装依赖”“同步源码”“通过 bootstrap 调视频号登录或上传”时使用。负责配置项目根目录、保存 Python 3.12 命令，并通过 skill 内脚本代理调用当前仓库的稳定入口。
---

# Longxia Bootstrap

本技能用于把当前仓库包装成一个可分发的 bootstrap 入口。

## 入口

- 脚本：`skills/longxia-bootstrap/scripts/bootstrap.py`
- 配置文件：`skills/longxia-bootstrap/project_config.json`
- 当前只开放平台：`shipinhao`

## 目标

1. 持久化项目根目录。
2. 持久化 Python 3.12 命令。
3. 检查依赖是否齐全。
4. 代理调用当前仓库的登录检查和视频号发布入口。

## 强制约束

1. 只能用 Python 3.12 运行 bootstrap 脚本。
2. `sync` 只允许在 git 工作区干净时执行。
3. bootstrap 当前只支持 `shipinhao`，不要扩写成四平台入口。

## 常用命令

查看状态：

```bash
/opt/homebrew/bin/python3.12 skills/longxia-bootstrap/scripts/bootstrap.py status
```

设置项目根目录：

```bash
/opt/homebrew/bin/python3.12 skills/longxia-bootstrap/scripts/bootstrap.py set-root /Users/mima0000/.openclaw/workspace/xiaolong-upload
```

设置 Python 3.12：

```bash
/opt/homebrew/bin/python3.12 skills/longxia-bootstrap/scripts/bootstrap.py set-python /opt/homebrew/bin/python3.12
```

安装依赖：

```bash
/opt/homebrew/bin/python3.12 skills/longxia-bootstrap/scripts/bootstrap.py install-deps
```

同步源码：

```bash
/opt/homebrew/bin/python3.12 skills/longxia-bootstrap/scripts/bootstrap.py sync
```

检查视频号登录：

```bash
/opt/homebrew/bin/python3.12 skills/longxia-bootstrap/scripts/bootstrap.py login-check --platform shipinhao
```

打开视频号登录：

```bash
/opt/homebrew/bin/python3.12 skills/longxia-bootstrap/scripts/bootstrap.py login --platform shipinhao
```

上传视频号：

```bash
/opt/homebrew/bin/python3.12 skills/longxia-bootstrap/scripts/bootstrap.py upload --platform shipinhao "<video_path>" "<title>" "<description>" "<tags>"
```

只做登录不发布：

```bash
/opt/homebrew/bin/python3.12 skills/longxia-bootstrap/scripts/bootstrap.py upload --platform shipinhao "<video_path>" --login-only
```

## 执行规则

1. 首次使用先执行 `status`。
2. 若 Python 3.12 未配置，先执行 `set-python`。
3. 若项目根目录未配置，先执行 `set-root`。
4. 若依赖缺失，再执行 `install-deps`。
5. 若用户只是要同步源码，先检查工作区是否干净；不干净就停住并说明原因。
