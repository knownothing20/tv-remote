# 一键更新到 GitHub 最新 Release
# 用法：双击 Update-Latest.cmd，或在 PowerShell 里运行本脚本
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot   # 脚本在 scripts\ 下，工程根目录是上一级
$Exe = Join-Path $Root "TrayTVAdmin.exe"
$Repo = "knownothing20/tv-remote"

Write-Host "==> 查询最新版本 ..." -ForegroundColor Cyan
try {
    $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" `
        -Headers @{ "User-Agent" = "tv-remote-updater" } -TimeoutSec 25
} catch {
    Write-Host "    查询失败：$($_.Exception.Message)" -ForegroundColor Red
    Write-Host "    提示：国内网络可能需要代理；也可直接访问 https://github.com/$Repo/releases/latest 手动下载"
    exit 1
}

$latest = ($rel.tag_name -replace '^v', '')
$asset = $rel.assets | Where-Object { $_.name -eq "TrayTVAdmin.exe" } | Select-Object -First 1
if (-not $asset) {
    Write-Host "    该 Release 没有 TrayTVAdmin.exe 资产" -ForegroundColor Red
    exit 1
}

$local = ""
$verFile = Join-Path $Root "local\version.txt"
if (Test-Path $verFile) { $local = ((Get-Content $verFile -Raw) -replace '\s', '') }
if (-not $local -and (Test-Path $Exe)) { $local = "已安装（未知版本）" }
Write-Host "    最新: v$latest   本地: $(if ($local) { 'v' + $local } else { '未安装' })"

Write-Host "==> 下载 $($asset.name)（$([math]::Round($asset.size / 1MB, 1)) MB）..." -ForegroundColor Cyan
$tmp = Join-Path $env:TEMP "TrayTVAdmin-$latest.exe"
try {
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $tmp -TimeoutSec 300 -UseBasicParsing
} catch {
    Write-Host "    下载失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# 运行中的托盘会占用 exe，先结束再替换
Get-Process TrayTVAdmin -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 600

try {
    Copy-Item $tmp $Exe -Force
    Remove-Item $tmp -Force
    Write-Host "==> 已更新到 v$latest" -ForegroundColor Green
} catch {
    Write-Host "    替换失败（文件可能被占用）：$($_.Exception.Message)" -ForegroundColor Red
    Write-Host "    请先在托盘右键「退出」，再重新运行本脚本"
    exit 1
}

Write-Host "    路径: $Exe"
Write-Host "    双击 TrayTVAdmin.lnk 即可启动最新版" -ForegroundColor DarkGray
