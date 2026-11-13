# 一键打包单文件 exe
# 用法: powershell -ExecutionPolicy Bypass -File scripts/build.ps1 [-Python python.exe]
param(
    [string]$Python = "python",
    [string]$Name = "TrayTVAdmin"
)

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$ErrorActionPreference = "Continue"

Write-Host "==> 安装依赖" -ForegroundColor Cyan
& $Python -m pip install -q --disable-pip-version-check -r requirements.txt 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Host "    pip 返回 $LASTEXITCODE（依赖已就绪时可忽略）" -ForegroundColor DarkYellow
}

Write-Host "==> PyInstaller 打包" -ForegroundColor Cyan
& $Python -m PyInstaller --noconfirm --clean --onefile --noconsole `
    --name $Name `
    --icon "assets/icons/tv_on.ico" `
    --add-data "src/tvremote/web;web" `
    --add-data "src/tvremote/adapters;tvremote/adapters" `
    --paths src `
    --hidden-import pystray._win32 `
    --hidden-import pystray._base `
    --hidden-import pystray._util.win32 `
    main.py 2>&1 | Out-Host

if ($LASTEXITCODE -ne 0) { throw "构建失败，退出码 $LASTEXITCODE" }

$exe = Join-Path $Root "dist\$Name.exe"
if (-not (Test-Path $exe)) { throw "未找到产物: $exe" }

$size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "==> 完成: $exe ($size MB)" -ForegroundColor Green
Write-Host "    自检: `"$exe`" --selftest" -ForegroundColor DarkGray
