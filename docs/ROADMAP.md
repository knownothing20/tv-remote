# 版本规划

## 版本策略

遵循 [语义化版本 2.0](https://semver.org/lang/zh-CN/)：`MAJOR.MINOR.PATCH`

| 位 | 触发条件 | 例子 |
|---|---|---|
| MAJOR | 破坏性变更：配置格式、API 路径、打包方式、最低 Python 版本 | 1.x → 2.0 |
| MINOR | 向后兼容的新功能 | 1.0 → 1.1 |
| PATCH | 修复、文案、样式、依赖升级 | 1.0.0 → 1.0.1 |

- **预发布**：`v1.2.0-beta.1`，发布为 GitHub Pre-release
- **分支**：`main` 保持可发布；功能走 `feat/<slug>`；发布走 `release/<version>`
- **发布流程**：更新 `src/tvremote/__init__.py` 的 `__version__` 与 `CHANGELOG.md` → 提交 → 打 tag `vX.Y.Z` → 推送
- **CI 产物**：Windows 单文件 exe（Release 附件）+ Docker 镜像（`ghcr.io/knownothing20/tv-remote`，amd64/arm64）
- **版本标签**：Docker 同时推 `:latest` 与 `:vX.Y.Z`

## 已发布

### v1.5.0 · 2026-11-13

面板体验。

- PWA：manifest + Service Worker + 图标，可添加到主屏
- 浅色 / 深色主题（跟随系统 + 手动切换）
- 内存趋势曲线（最近 180 个采样点）

### v1.4.0 · 2026-11-13

更新检查。

- 面板「可更新 vX.Y.Z」提示，点击跳转 Release
- `GET /api/update`，30 分钟缓存，失败静默降级
- 设置项 `check_updates` 可关闭

### v1.3.0 · 2026-11-13

应用管理。

- 面板「应用管理」卡片：搜索、第三方/全部切换
- 打开 / 停止 / 停用 / 启用 / 清除数据 / 卸载
- 危险操作二次确认，关键系统组件保护名单
- `GET /api/apps`、`POST /api/app`

### v1.2.0 · 2026-11-13

多设备管理。

- `local/devices.json`：多台电视的名称 / 地址 / adb 路径，支持增删改
- 面板顶部设备下拉 + 「设备」管理弹窗
- 托盘「设备」二级菜单（单选切换，即时生效）
- `GET/POST /api/devices`，切换后热重建 ADB 客户端并清空缓存

### v1.1.0 · 2026-11-13

- **局域网访问**：新增 `host` 配置（`0.0.0.0` 即可让同网段设备打开面板）
- **可选访问口令**：`token` 配置，请求需带 `?token=` 或 `X-Auth-Token`
- **Docker / 无界面版**：`--headless` 模式 + `Dockerfile` + `docker-compose.yml`，CI 推送多架构镜像到 GHCR
- adb 掉线自动重连（容器与远程场景必需）
- 版本号贯通托盘 tooltip、面板徽标与 `/api/status`

### v1.0.0 · 2026-11-13

首个公开版本：托盘单文件应用、双态图标、Web 面板、MJPEG 实时画面、快捷操作、
`local/` 目录隔离、隐私脱敏、模块化源码与 CI。

## 路线图

### v2.0.0 · 插件化与跨平台

- 采集器插件化：每类信息一个 provider（硬件 / 网络 / 应用 / 自启）
- macOS 与 Linux 托盘（`pystray` 已支持，需补平台适配）
- 评估更轻的壳层（如 Tauri）以减小体积

## 明确不做

- 绕过厂商的安装校验 / 破解类功能
- 任何形式的数据上传（全部数据留在本地）
- 内建自动更新（仅提示，由用户决定）
- 把面板默认暴露到公网（需要口令，且建议只在内网使用）
