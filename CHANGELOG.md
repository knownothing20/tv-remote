# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。版本策略与路线图见 [docs/ROADMAP.md](docs/ROADMAP.md)。

## [1.5.1] - 2026-11-13

补丁：为「一键更新」提供本地版本标识。

### Added

- 启动时写入 `local/version.txt`，供 `Update-Latest.ps1` 比对本地版本
- `--selftest` 输出新增 `version` 字段
- 仓库提供 `Update-Latest.ps1` / `Update-Latest.cmd`（下载并替换为 GitHub 最新 Release）
- `scripts/make_shortcut.py`：不依赖 COM 生成 `.lnk` 快捷方式
- `Start-Tray.cmd`：备用启动器

## [1.5.0] - 2026-11-13

面板体验。

### Added

- **PWA**：`manifest.webmanifest` + Service Worker + 192/512 图标，手机 / iPad 可「添加到主屏」独立打开
- **浅色 / 深色主题**：跟随系统，右上角 ◐ 手动切换，选择存 localStorage
- **内存趋势图**：服务端保留最近 180 个采样点，面板用 canvas 绘制 3 分钟曲线
- `GET /api/history`

### Changed

- 面板配色全面改为 CSS 变量，主题切换无闪烁

## [1.4.0] - 2026-11-13

更新检查。

### Added

- 面板顶部显示「可更新 vX.Y.Z」，点击跳转对应 Release（只提示，不自动下载）
- `GET /api/update`：查询 GitHub Releases 最新版本，30 分钟缓存，失败静默降级
- 设置项 `check_updates`（默认开启），可在「设备」弹窗内关闭

## [1.3.0] - 2026-11-13

应用管理。

### Added

- 面板新增「应用管理」卡片：按包名搜索、第三方 / 全部应用切换
- 应用操作：打开、停止、停用、启用、清除数据、卸载（`pm` / `am`）
- 危险操作二次确认；关键系统组件（systemui / settings / packageinstaller 等）加入保护名单
- `GET /api/apps?scope=third|all&q=`、`POST /api/app`（cmd: open/stop/disable/enable/clear/uninstall）
- 包名白名单校验，拒绝非 `[A-Za-z0-9_.]` 输入

## [1.2.0] - 2026-11-13

多设备管理。

### Added

- `local/devices.json`：多台电视的名称 / 地址 / adb 路径，支持增删改
- 面板顶部设备下拉框 + 「设备」管理弹窗（新增 / 切换 / 删除）
- 托盘「设备」二级菜单：单选项切换，切换即时生效
- `GET/POST /api/devices`：`select` / `add` / `update` / `remove`
- 切换设备会同步写入 `local/config.json`，并热重建 ADB 客户端、清空缓存

## [1.1.0] - 2026-11-13

局域网访问与容器化部署。

### Added

- `host` 配置项：设为 `0.0.0.0` 后同网段设备可直接打开面板
- `token` 配置项：可选访问口令，支持 `?token=` 与 `X-Auth-Token`
- `--headless` 无界面模式，Dockerfile / docker-compose.yml / docs/DOCKER.md
- CI 新增 Docker 任务：推送 `ghcr.io/knownothing20/tv-remote:latest` 与 `:vX.Y.Z`（amd64 + arm64）
- `/api/status` 返回版本号；面板徽标与托盘 tooltip 显示版本
- adb 掉线后自动 `connect` 重试一次（容器与远程场景）

## [1.0.0] - 2026-11-13

首个公开版本。

- 托盘单文件应用：双击启动，右键菜单（打开面板 / 复制地址 / 重启服务 / 退出即停服务）
- 双态图标：屏幕黑=未连接、屏幕亮=已连接，5 秒轮询 `/api/ping`
- 本地 Web 面板：硬件、内存、存储、网络、前台应用、进程 Top、后台服务、自启动清单、省电白名单
- MJPEG 实时画面（约 1 fps，单路）
- 快捷操作：打开投屏 App / 回桌面 / 返回键 / 加白名单 / 保存截图
- 配置外置：`local/config.json` + 环境变量 + 命令行参数
- **隐私脱敏**：IP / 序列号 / Wi-Fi 名称默认打码，面板可切换，日志兜底遮蔽
- **`local/` 目录隔离**：配置、设置、日志、截图统一存放且不进仓库
- 模块化源码（`src/tvremote`）、图标生成器、一键打包脚本与 GitHub Actions 工作流
