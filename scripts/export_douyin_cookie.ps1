# Export Douyin cookies from connected Chrome (port 9224)
# Usage:
#   .\export_douyin_cookie.ps1
#   .\export_douyin_cookie.ps1 -OutputFile C:\path\douyin_cookie.json
# 未指定 -OutputFile 时写入默认 cookie 目录下的 dy.json

param(
    [string]$OutputFile = ""
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$profileDir = Join-Path $projectRoot "cookies\chrome_connect_dy"
$port = 9224
$url = "https://creator.douyin.com/creator-micro/content/upload"

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    . (Join-Path $scriptDir "cookie_path_utils.ps1")
    $defaultDir = Get-LongxiaDefaultCookieDir -ProjectRoot $projectRoot
    New-Item -ItemType Directory -Force -Path $defaultDir | Out-Null
    $OutputFile = Join-Path $defaultDir "dy.json"
}

$chrome = $env:LOCAL_CHROME_PATH
if (-not $chrome) {
    $chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
    if (-not (Test-Path $chrome)) {
        $chrome = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    }
}

$listening = netstat -ano 2>$null | Select-String "127.0.0.1:$port\s+.*LISTENING"
if (-not $listening) {
    Write-Host "Starting Chrome with remote debugging (port $port)..."
    New-Item -ItemType Directory -Force -Path $profileDir | Out-Null
    Start-Process -FilePath $chrome -ArgumentList "--remote-debugging-port=$port", "--user-data-dir=$profileDir", "--start-maximized", $url -WindowStyle Maximized
    Write-Host "Waiting for Chrome..."
    Start-Sleep -Seconds 5
}

Push-Location $projectRoot
try {
    $env:PYTHONIOENCODING = "utf-8"
    python -u "$scriptDir\export_cookie_cdp_raw.py" --port $port --output $OutputFile --timeout 12
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
