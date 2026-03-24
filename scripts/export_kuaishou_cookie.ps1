# Export Kuaishou cookies from connected Chrome (port 9225)
# Usage:
#   .\export_kuaishou_cookie.ps1
#   .\export_kuaishou_cookie.ps1 -OutputFile C:\path\ks_cookie.json

param(
    [string]$OutputFile = ""
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$profileDir = Join-Path $projectRoot "cookies\chrome_connect_ks"
$port = 9225
$url = "https://cp.kuaishou.com/article/publish/video"

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = Join-Path $projectRoot "cookies\kuaishou\cookie_exported.json"
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
    python -u "$scriptDir\export_cookie_cdp_raw.py" --port $port --url $url --output $OutputFile --timeout 12
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
