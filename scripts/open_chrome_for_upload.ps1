# Windows: 启动带远程调试的 Chrome，供上传脚本连接
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$profileDir = Join-Path $projectRoot "cookies\chrome_connect"
$chrome = $env:LOCAL_CHROME_PATH
if (-not $chrome) {
    $chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
    if (-not (Test-Path $chrome)) {
        $chrome = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    }
}
New-Item -ItemType Directory -Force -Path $profileDir | Out-Null
Write-Host "启动上传用 Chrome (connect 模式)"
& $chrome --remote-debugging-port=9222 "--user-data-dir=$profileDir" "https://creator.douyin.com/creator-micro/content/upload"
