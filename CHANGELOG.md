# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。版本策略与路线图见 [docs/ROADMAP.md](docs/ROADMAP.md)。

## [1.6.0] - 2026-11-13

机型适配器（package → 中文名）。

### Added

- `src/tvremote/adapters/<id>.json`：按 `ro.product.model` / `ro.product.brand` 匹配机型的包名映射表，
  每条含中文名、角色（system/tcl/media/thirdparty）与处置策略（avoid/keep/optional/bloat）
- 面板：进程 Top、后台服务、自启动、应用列表都显示中文名 + 策略标签（悬停看说明），头部显示当前适配器
- `GET /api/adapter`；`/api/status` 增加 `adapter` 字段
- 内置 `tcl_mt5879_cn`（57 条，参考机型 TCL 65Q10K / MT5879 / Android 11）
- `adapters/_template.json` 与 `docs/ADAPTERS.md`（新增机型约 20 分钟）

### Changed

- 打包脚本增加 `--add-data src/tvremote/adapters`，exe 内置适配器数据

## [1.5.9] - 2026-11-13

### Added

- **投屏时自动切前台**（`foreground_on_cast`，默认开启）：看门狗检测到接收端端口（7000）
  存在已建立连接时，自动把 CastBay 切到前台。
  原因：映湾退到后台后系统销毁渲染 Surface，音频仍播放但**画面全黑**（用户实测确认）。
- 看门狗上移至 `make_server()`，托盘模式与 headless 模式行为一致。
- 面板「设备」弹窗新增对应开关。

## [1.5.8] - 2026-11-13

### Changed

- 守护改为**静默拉起**（设置项 `silent_launch`，默认开启）：拉起接收端后约 1.4 秒自动退回
  原来的应用 / 桌面，不会把映湾界面留在电视上。
- 守护前先检查媒体播放状态：**正在播放视频/音乐时不打扰**。
- 面板「设备」弹窗新增「静默拉起（不留在映湾界面）」开关。

## [1.5.7] - 2026-11-13

### Added

- **投屏接收端守护**：设置项 `auto_launch_receiver`（面板「设备」弹窗内开关）。
  开启后，只要电视在线而 CastBay 未运行，服务会自动拉起它（60 秒节流，避免与手动关闭打架）。
  背景：CastBay 没有后台服务组件，Android 11 又限制开机广播拉起界面，电视重启后不保证自启。
- `serve()` 增加看门狗线程：headless / Docker 模式无人访问面板时也会持续心跳与守护。

## [1.5.6] - 2026-11-13

### Changed

- 监听 `0.0.0.0`（局域网模式）时，托盘「打开管理后台」「复制访问地址」「设备管理」
  改用**本机局域网 IP**（新增 `Config.public_url` 与 `lan_ip()`），不再是 `127.0.0.1`，
  复制出来即可直接发给 iPad / 手机。
- 内部心跳轮询仍走 `127.0.0.1`，不受防火墙与网卡切换影响。

## [1.5.5] - 2026-11-13

### Fixed

- **托盘「打开管理后台」被 401 挡住**：启用 `token` 后面板需要口令，而菜单打开的是不带
  口令的裸地址。现在「打开管理后台」「复制访问地址」「设备管理」都会自动附带 `?token=`。
- 未带口令访问首页时，返回可读的 HTML 提示页（说明口令位置与正确地址），不再是无提示的
  `{"error":"unauthorized"}` JSON。

## [1.5.4] - 2026-11-13

### Fixed

- **托盘启动即崩溃**：设备子菜单的回调用了带默认值的第三个参数，pystray 的
  `_assert_action` 抛 `ValueError`，双击 exe / 快捷方式会弹
  「Unhandled exception in script」。已改为闭包工厂生成 0~2 参数回调。
- `--selftest` 新增 `tray_menu_ok`：真实构建含设备子菜单的菜单，覆盖此类签名错误。

### Changed

- `Update-Latest.ps1` 移入 `scripts/`，根目录只保留 `Update-Latest.cmd` 入口

## [1.5.3] - 2026-11-13

### Fixed

- **托盘心跳未携带访问口令**：启用 `token` 后 `/api/ping` 返回 401，被误判为离线，
  表现为托盘图标一直黑屏、`--selftest` 报 `device_online: false`。
  现在心跳请求会自动附带 `?token=`。

## [1.5.2] - 2026-11-13

### Fixed

- 自检/托盘心跳的超时竞态：客户端 2.5 秒超时 < 服务端首次 adb 探测 3 秒，
  导致 `--selftest` 误报 `device_online: false`、托盘图标偶发黑屏。改为 6 秒（自检 15 秒）。

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
