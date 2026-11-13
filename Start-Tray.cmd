@echo off
rem 备用启动器：万一 .lnk 快捷方式被安全软件拦截，可双击本文件启动
cd /d "%~dp0"
start "" "%~dp0TrayTVAdmin.exe"
