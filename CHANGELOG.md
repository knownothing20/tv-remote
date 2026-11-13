# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。版本策略与路线图见 [docs/ROADMAP.md](docs/ROADMAP.md)。

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
