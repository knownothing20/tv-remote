@echo off
chcp 65001 >nul
title 更新电视管理后台到最新版
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Update-Latest.ps1"
echo.
pause
