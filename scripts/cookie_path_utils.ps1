# Shared: default cookie directory for import/export.
# Override: env LONGXIA_COOKIE_DIR（绝对路径）。
# 项目根 config\default_cookie_dir.txt 第一行为 cookie 目录（通常为 ...\归档(1)\cookies）。

function Get-LongxiaDefaultCookieDir {
    param([Parameter(Mandatory = $true)] [string]$ProjectRoot)

    $fromEnv = $env:LONGXIA_COOKIE_DIR
    if ($fromEnv -and $fromEnv.Trim()) {
        return $fromEnv.Trim()
    }

    $cfg = Join-Path $ProjectRoot "config\default_cookie_dir.txt"
    if (Test-Path -LiteralPath $cfg) {
        $line = Get-Content -LiteralPath $cfg -Encoding UTF8 -TotalCount 1 -ErrorAction SilentlyContinue
        if ($line -and $line.Trim()) {
            return $line.Trim()
        }
    }

    $desktop = [Environment]::GetFolderPath("Desktop")
    $archiveCfg = Join-Path $desktop "归档(1)\config\default_cookie_dir.txt"
    if (Test-Path -LiteralPath $archiveCfg) {
        $line = Get-Content -LiteralPath $archiveCfg -Encoding UTF8 -TotalCount 1 -ErrorAction SilentlyContinue
        if ($line -and $line.Trim()) {
            return $line.Trim()
        }
    }

    return (Join-Path $env:USERPROFILE "Desktop\归档(1)\cookies")
}

function Get-LongxiaPlatformCookieFileName {
    param([Parameter(Mandatory = $true)] [string]$Platform)
    switch ($Platform) {
        "xiaohongshu" { return "xhs.json" }
        "douyin" { return "dy.json" }
        "kuaishou" { return "ks.json" }
        "shipinhao" { return "sph.json" }
        default { throw "unknown platform: $Platform" }
    }
}

function Resolve-LongxiaCookiePath {
    param(
        [Parameter(Mandatory = $true)] [string]$ProjectRoot,
        [Parameter(Mandatory = $true)] [string]$CookieFile
    )

    if ([string]::IsNullOrWhiteSpace($CookieFile)) {
        return $CookieFile
    }

    if (Test-Path -LiteralPath $CookieFile) {
        return (Resolve-Path -LiteralPath $CookieFile).Path
    }

    $base = Get-LongxiaDefaultCookieDir -ProjectRoot $ProjectRoot
    $candidate = Join-Path $base $CookieFile
    if (Test-Path -LiteralPath $candidate) {
        return (Resolve-Path -LiteralPath $candidate).Path
    }

    return $CookieFile
}
