@echo off
chcp 65001 >nul
REM Windows 双击运行 - 统一上传（使用根目录 .venv）
REM 用法: 传入参数给 upload.py，如 -p kuaishou 视频路径 "标题" "文案" "标签"
cd /d "%~dp0\.."
if not exist .venv\Scripts\python.exe (
    echo 创建虚拟环境...
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
)
.venv\Scripts\python.exe upload.py %*
pause
