#!/usr/bin/env pwsh
# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    龙虾上传项目一键部署脚本 - 专为 openclaw 设计

.DESCRIPTION
    自动完成 longxia-upload 项目的环境检查、依赖安装和验证

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File deploy.ps1

.EXAMPLE
    .\deploy.ps1 -Quick
#>

param(
    [switch]$Quick,          # 快速模式，跳过部分检查
    [switch]$Verbose,        # 详细输出
    [string]$ProjectPath = "C:\Users\爽爽\Desktop\shuang\xiaolong-upload"
)

# 设置输出编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$PROJECT_ROOT = Resolve-Path $ProjectPath
$PYTHON_MIN_VERSION = "3.10"

function Write-Step {
    param([string]$Message)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "  ✓ $Message" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "  ✗ $Message" -ForegroundColor Red
}

function Test-PythonVersion {
    Write-Step "检查 Python 版本"

    try {
        $pythonVersion = & python --version 2>&1
        Write-Host "  当前 Python: $pythonVersion"

        $version = [System.Version]::Parse(($pythonVersion -replace 'Python\s*', '').Trim())
        $minVersion = [System.Version]::Parse($PYTHON_MIN_VERSION)

        if ($version -ge $minVersion) {
            Write-Success "Python 版本符合要求 (>= $PYTHON_MIN_VERSION)"
            return $true
        } else {
            Write-Error-Custom "Python 版本过低，需要 >= $PYTHON_MIN_VERSION"
            return $false
        }
    } catch {
        Write-Error-Custom "未找到 Python，请先安装 Python 3.10+"
        return $false
    }
}

function Test-ProjectPath {
    Write-Step "检查项目目录"

    if (Test-Path $PROJECT_ROOT) {
        Write-Success "项目目录存在：$PROJECT_ROOT"

        $requiredFiles = @("upload.py", "pyproject.toml", "requirements.txt")
        $missing = @()

        foreach ($file in $requiredFiles) {
            if (-not (Test-Path (Join-Path $PROJECT_ROOT $file))) {
                $missing += $file
            }
        }

        if ($missing.Count -eq 0) {
            Write-Success "项目文件完整"
            return $true
        } else {
            Write-Error-Custom "缺少文件：$($missing -join ', ')"
            return $false
        }
    } else {
        Write-Error-Custom "项目目录不存在：$PROJECT_ROOT"
        return $false
    }
}

function Install-Dependencies {
    Write-Step "安装依赖"

    Set-Location $PROJECT_ROOT

    Write-Host "  执行：pip install -e .`n"

    # 尝试使用清华镜像源
    $mirrorUrl = "https://pypi.tuna.tsinghua.edu.cn/simple"

    try {
        & pip install -e . -i $mirrorUrl 2>&1 | ForEach-Object {
            Write-Host "    $_"
        }

        if ($LASTEXITCODE -eq 0) {
            Write-Success "依赖安装成功"
            return $true
        } else {
            throw "pip install failed"
        }
    } catch {
        Write-Host "  镜像源失败，尝试官方源..." -ForegroundColor Yellow

        try {
            & pip install -e . 2>&1 | ForEach-Object {
                Write-Host "    $_"
            }

            if ($LASTEXITCODE -eq 0) {
                Write-Success "依赖安装成功"
                return $true
            } else {
                Write-Error-Custom "依赖安装失败"
                return $false
            }
        } catch {
            Write-Error-Custom "依赖安装失败：$($_.Exception.Message)"
            return $false
        }
    }
}

function Verify-Installation {
    Write-Step "验证安装"

    Set-Location $PROJECT_ROOT

    # 方法 1: 检查 longxia-upload 命令
    $cliExists = $false
    try {
        $result = & longxia-upload --help 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "longxia-upload 命令可用"
            $cliExists = $true
        }
    } catch {}

    # 方法 2: 检查 python upload.py
    if (-not $cliExists) {
        try {
            $result = & python upload.py --help 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Success "python upload.py 可用"
            } else {
                Write-Error-Custom "验证失败"
                return $false
            }
        } catch {
            Write-Error-Custom "验证失败：$($_.Exception.Message)"
            return $false
        }
    }

    return $true
}

function Show-Usage {
    Write-Host @"

========================================
  部署完成！
========================================

使用方式:

  # 单平台上传
  longxia-upload -p douyin "视频路径.mp4" "标题" "文案" "标签 1,标签 2"

  # 或使用 Python 直接运行
  python upload.py --platform douyin "视频路径.mp4"

支持平台：douyin, kuaishou, shipinhao, xiaohongshu

"@ -ForegroundColor Green
}

# ==================== 主流程 ====================

Write-Host @"
========================================
  龙虾上传 (Longxia Upload) 一键部署
========================================
"@ -ForegroundColor Cyan

$steps = @(
    @{Name = "Python 版本检查"; Func = {Test-PythonVersion}},
    @{Name = "项目目录检查"; Func = {Test-ProjectPath}},
    @{Name = "依赖安装"; Func = {Install-Dependencies}},
    @{Name = "安装验证"; Func = {Verify-Installation}}
)

$results = @()

foreach ($step in $steps) {
    $result = & $step.Func
    $results += $result

    if (-not $result -and -not $Quick) {
        Write-Host "`n部署中断于：$($step.Name)" -ForegroundColor Red
        Write-Host "请检查上述错误信息后重试" -ForegroundColor Yellow
        exit 1
    }
}

if ($results[-1]) {
    Show-Usage
    exit 0
} else {
    Write-Host "`n部署完成但存在警告" -ForegroundColor Yellow
    exit 1
}
