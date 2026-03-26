# Douyin upload - Connect mode (attach to Chrome with remote debugging)
# Usage: .\upload_douyin_connect.ps1 "video" "title" [description] [tags]
#
# Env (optional):
#   UPLOAD_CLOSE_BROWSER_DELAY   Seconds after success before closing Chrome. Default 10. 0 or never = never close.
#   UPLOAD_CLOSE_BROWSER_ON_FAIL  Set to 1 or true to close browser on failure too.

param(
    [Parameter(Mandatory=$true)] [string]$VideoPath,
    [Parameter(Mandatory=$true)] [string]$Title,
    [string]$Description = "",
    [string]$Tags = ""
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$profileDir = Join-Path $projectRoot "cookies\chrome_connect_dy"
$port = 9224

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
    Start-Process -FilePath $chrome -ArgumentList "--remote-debugging-port=$port", "--user-data-dir=$profileDir", "--start-maximized", "https://creator.douyin.com/creator-micro/content/upload" -WindowStyle Maximized
    Write-Host "Waiting for Chrome..."
    Start-Sleep -Seconds 5
}

$env:AUTH_MODE = "connect"
$env:CDP_DEBUG_PORT = [string]$port
$env:CDP_ENDPOINT = "http://127.0.0.1:$port"
$env:PYTHONIOENCODING = "utf-8"

Push-Location $projectRoot
$uploadExit = 1
try {
    python upload.py --platform douyin $VideoPath $Title $Description $Tags
    $uploadExit = $LASTEXITCODE
    if ($null -eq $uploadExit) { $uploadExit = 0 }
} finally {
    Pop-Location
}

$delayRaw = $env:UPLOAD_CLOSE_BROWSER_DELAY
$onFail = $env:UPLOAD_CLOSE_BROWSER_ON_FAIL
$shouldClose = ($uploadExit -eq 0) -or ($onFail -eq "1") -or ($onFail -ieq "true")

if (-not $shouldClose) {
    Write-Host "Upload failed (exit $uploadExit). Debug Chrome left open."
    exit $uploadExit
}

$delaySec = 10
if ($null -ne $delayRaw -and $delayRaw.Trim().Length -gt 0) {
    $trim = $delayRaw.Trim()
    $lower = $trim.ToLower()
    if ($lower -eq "never") {
        Write-Host "UPLOAD_CLOSE_BROWSER_DELAY=never, not closing browser."
        exit $uploadExit
    }
    $maybeDelay = 0
    $parsedOk = [int]::TryParse($trim, [ref]$maybeDelay)
    if ($parsedOk) {
        $delaySec = $maybeDelay
    }
}

if ($delaySec -le 0) {
    Write-Host "UPLOAD_CLOSE_BROWSER_DELAY<=0, not closing browser."
    exit $uploadExit
}

Write-Host "Upload OK. Closing debug Chrome in $delaySec s..."
Start-Sleep -Seconds $delaySec
Get-CimInstance Win32_Process -Filter "name='chrome.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*$profileDir*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Write-Host "Browser closed."
exit $uploadExit
