---
name: longxia-bootstrap
description: Bootstrap 技能。当用户提到“安装后直接能用”“初始化项目”“配置项目根目录”“配置 Python 3.12”“检查环境”“安装依赖”“同步源码”“通过 skill 调登录检查/视频号上传”时使用。负责定位 xiaolong-upload 项目根目录、配置跨平台 Python 3.12、检查依赖并通过 skill 内脚本代理调用项目里的登录检查和视频号发布入口。
---

# Longxia Bootstrap

本技能用于把当前仓库包装成一个可分发的 bootstrap skill。

目标：

1. skill 安装后先检查项目根目录、Python 3.12 和依赖。
2. 将项目根目录持久化在 skill 自己的配置文件里。
3. 将 Python 3.12 命令持久化在 skill 自己的配置文件里，兼容 macOS 和 Windows。
4. 后续通过 skill 自带脚本代理调用项目中的登录检查和视频号上传入口。
5. 当前只暴露视频号；其他平台实现留在项目里，不在 bootstrap 入口暴露。

## 强制约束

- Python 一律使用 3.12
- 严禁使用 3.12 之外的 Python 版本
- macOS 推荐：`/opt/homebrew/bin/python3.12`
- Windows 推荐：`py -3.12`
- 当前 bootstrap skill 只允许 `shipinhao`

## 可执行脚本

脚本路径：

```bash
skills/longxia-bootstrap/scripts/bootstrap.py
```

常用命令：

查看当前状态：

```bash
python3.12 skills/longxia-bootstrap/scripts/bootstrap.py status
```

设置项目根目录：

```bash
python3.12 skills/longxia-bootstrap/scripts/bootstrap.py set-root /abs/path/to/xiaolong-upload
```

设置 Python 3.12 命令：

```bash
python3.12 skills/longxia-bootstrap/scripts/bootstrap.py set-python /opt/homebrew/bin/python3.12
```

安装依赖：

```bash
python3.12 skills/longxia-bootstrap/scripts/bootstrap.py install-deps
```

同步项目最新代码：

```bash
python3.12 skills/longxia-bootstrap/scripts/bootstrap.py sync
```

检查视频号登录：

```bash
python3.12 skills/longxia-bootstrap/scripts/bootstrap.py login-check --platform shipinhao
```

打开视频号登录并等待：

```bash
python3.12 skills/longxia-bootstrap/scripts/bootstrap.py login --platform shipinhao
```

发布视频号：

```bash
python3.12 skills/longxia-bootstrap/scripts/bootstrap.py upload --platform shipinhao "<video_path>" "<title>" "<description>" "<tags>"
```

macOS 推荐实际调用：

```bash
/opt/homebrew/bin/python3.12 skills/longxia-bootstrap/scripts/bootstrap.py set-python /opt/homebrew/bin/python3.12
```

Windows 推荐实际调用：

```powershell
py -3.12 skills/longxia-bootstrap/scripts/bootstrap.py set-python py -3.12
```

## 执行流程

1. 首次使用先跑 `status`
2. 如果 Python 3.12 命令未配置或自动探测失败，跑 `set-python`
3. 如果项目根目录未配置，跑 `set-root`
4. 如果依赖未安装，跑 `install-deps`
5. 若用户说“按最新代码更新”“同步源码”，跑 `sync`
6. 需要登录时跑 `login-check` 或 `login`
7. 需要发布时跑 `upload`

## 设计边界

- 本 skill 不复制项目源码，只做 bootstrap 和代理调用
- 真正的业务逻辑仍由项目内的 `upload.py`、`skills/auth/scripts/platform_login.py` 等脚本执行
- 若项目根目录不存在或缺关键文件，必须明确报错并停止
- `sync` 只允许在 git 工作区干净时执行；若存在未提交改动，必须停止并明确提示，不能自动覆盖用户源码
