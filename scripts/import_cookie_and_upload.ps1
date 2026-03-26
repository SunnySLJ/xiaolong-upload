# Cookie import + upload (connect mode)
# Usage:
#   .\import_cookie_and_upload.ps1 -Platform douyin -VideoPath ... -Title ...   # 默认 cookies/dy.json（目录见 config\default_cookie_dir.txt）
#   .\import_cookie_and_upload.ps1 -Platform douyin -CookieFile dy.json -ValidateOnly
# CookieFile 省略时按平台使用 xhs.json / dy.json / ks.json / sph.json；亦可绝对路径或仅文件名。

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("douyin", "xiaohongshu", "kuaishou", "shipinhao")]
    [string]$Platform,

    [string]$CookieFile = "",

    [string]$VideoPath = "",
    [string]$Title = "",
    [string]$Description = "",
    [string]$Tags = "",

    [switch]$ValidateOnly
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

. (Join-Path $scriptDir "cookie_path_utils.ps1")
if ([string]::IsNullOrWhiteSpace($CookieFile)) {
    $base = Get-LongxiaDefaultCookieDir -ProjectRoot $projectRoot
    $CookieFile = Join-Path $base (Get-LongxiaPlatformCookieFileName -Platform $Platform)
} else {
    $CookieFile = Resolve-LongxiaCookiePath -ProjectRoot $projectRoot -CookieFile $CookieFile
}

if (-not (Test-Path -LiteralPath $CookieFile)) {
    Write-Host "Cookie file not found: $CookieFile"
    exit 1
}

$chrome = $env:LOCAL_CHROME_PATH
if (-not $chrome) {
    $chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
    if (-not (Test-Path $chrome)) {
        $chrome = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    }
}

$port = 9224
$profileDir = Join-Path $projectRoot "cookies\chrome_connect_dy"
$url = "https://creator.douyin.com/creator-micro/content/upload"
$uploadScript = Join-Path $scriptDir "upload_douyin_connect.ps1"

if ($Platform -eq "xiaohongshu") {
    $port = 9223
    $profileDir = Join-Path $projectRoot "cookies\chrome_connect_xhs"
    $url = "https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video"
    $uploadScript = Join-Path $scriptDir "upload_xiaohongshu_connect.ps1"
}
elseif ($Platform -eq "kuaishou") {
    $port = 9225
    $profileDir = Join-Path $projectRoot "cookies\chrome_connect_ks"
    $url = "https://cp.kuaishou.com/article/publish/video"
    $uploadScript = Join-Path $scriptDir "upload_kuaishou_connect.ps1"
}
elseif ($Platform -eq "shipinhao") {
    $port = 9226
    $profileDir = Join-Path $projectRoot "cookies\chrome_connect_sph"
    $url = "https://channels.weixin.qq.com/platform/post/create"
    $uploadScript = Join-Path $scriptDir "upload_shipinhao_connect.ps1"
}

$listening = netstat -ano 2>$null | Select-String "127.0.0.1:$port\s+.*LISTENING"
if (-not $listening) {
    Write-Host "Starting Chrome for $Platform (port $port)..."
    New-Item -ItemType Directory -Force -Path $profileDir | Out-Null
    Start-Process -FilePath $chrome -ArgumentList "--remote-debugging-port=$port", "--user-data-dir=$profileDir", "--start-maximized", $url -WindowStyle Maximized
    Start-Sleep -Seconds 5
}

$env:AUTH_MODE = "connect"
$env:CDP_DEBUG_PORT = [string]$port
$env:CDP_ENDPOINT = "http://127.0.0.1:$port"
$env:PYTHONIOENCODING = "utf-8"

Push-Location $projectRoot
try {
    $check = python "$scriptDir\import_cookie_to_connect.py" --platform $Platform --port $port --url $url --cookie-file "$CookieFile"
    if ($LASTEXITCODE -ne 0) {
        Write-Host $check
        Write-Host "Cookie validation failed. Upload aborted."
        exit $LASTEXITCODE
    }
    Write-Host $check

    if ($ValidateOnly) {
        Write-Host "ValidateOnly enabled. Stop after cookie validation."
        exit 0
    }

    if ([string]::IsNullOrWhiteSpace($VideoPath) -or [string]::IsNullOrWhiteSpace($Title)) {
        Write-Host "VideoPath and Title are required when not using -ValidateOnly."
        exit 1
    }

    powershell -NoProfile -ExecutionPolicy Bypass -File $uploadScript $VideoPath $Title $Description $Tags
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
