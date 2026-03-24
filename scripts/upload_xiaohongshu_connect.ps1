# 小红书上传统用脚本 - Connect 模式（连接已打开的 Chrome）
# 用法: .\upload_xiaohongshu_connect.ps1 "视频路径" "标题" [文案] [标签]
# 若未启动 Chrome，会先启动带远程调试的 Chrome

param(
    [Parameter(Mandatory=$true)] [string]$VideoPath,
    [Parameter(Mandatory=$true)] [string]$Title,
    [string]$Description = "",
    [string]$Tags = ""
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$profileDir = Join-Path $projectRoot "cookies\chrome_connect_xhs"
$port = 9223

# Chrome 路径
$chrome = $env:LOCAL_CHROME_PATH
if (-not $chrome) {
    $chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
    if (-not (Test-Path $chrome)) {
        $chrome = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    }
}

# 检查 9223 端口是否有 Chrome
$listening = netstat -ano 2>$null | Select-String "127.0.0.1:$port\s+.*LISTENING"
if (-not $listening) {
    Write-Host "启动带远程调试的 Chrome (端口 $port)..."
    New-Item -ItemType Directory -Force -Path $profileDir | Out-Null
    Start-Process -FilePath $chrome -ArgumentList "--remote-debugging-port=$port", "--user-data-dir=$profileDir", "--start-maximized", "https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video" -WindowStyle Maximized
    Write-Host "等待 Chrome 就绪..."
    Start-Sleep -Seconds 5
}

# 执行上传
$env:AUTH_MODE = "connect"
$env:CDP_DEBUG_PORT = [string]$port
$env:CDP_ENDPOINT = "http://127.0.0.1:$port"
$env:PYTHONIOENCODING = "utf-8"

Push-Location $projectRoot
try {
    python upload.py --platform xiaohongshu $VideoPath $Title $Description $Tags
} finally {
    Pop-Location
}

# 上传结束后等待 10 秒再关闭浏览器
Write-Host "上传完成，10 秒后关闭浏览器..."
Start-Sleep -Seconds 10
Get-CimInstance Win32_Process -Filter "name='chrome.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*$profileDir*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Write-Host "已关闭浏览器"
