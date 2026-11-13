# 架构说明

## 组件

```
┌────────────────────────── TrayTVAdmin.exe ──────────────────────────┐
│                                                                     │
│  tray.py ──► pystray.Icon ──► 托盘图标（黑屏 / 亮屏）                │
│     │              ▲                                                 │
│     │              └── 5s 轮询 GET /api/ping                        │
│     │                                                               │
│     └──► Backend ──► server.py (ThreadingHTTPServer, 127.0.0.1)      │
│                          │                                           │
│                          ├── GET /            → web/index.html       │
│                          ├── GET /api/status  → 采集器（adb shell）  │
│                          ├── GET /api/ping    → adb shell echo ok    │
│                          ├── GET /api/screen  → exec-out screencap   │
│                          └── POST /api/action → input keyevent ...   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ adb over TCP 5555
                        ┌──────▼──────┐
                        │  Android TV │
                        └─────────────┘
```

## 模块职责

| 模块 | 职责 |
|---|---|
| `config.py` | 合并「默认值 → `local/config.json` → 环境变量 → 命令行」，产出 `Config`；同时管理 `local/` 目录、`Settings` 持久化 |
| `privacy.py` | 脱敏：IP、ADB 地址、序列号、SSID、MAC，以及日志文本里的 IPv4 |
| `adb.py` | 定位 `adb` 可执行文件；`run()` 返回原始字节，`shell()` 返回文本 |
| `server.py` | 采集器（内存/存储/网络/进程/服务/自启动）、HTTP 路由、MJPEG 推流 |
| `tray.py` | 托盘菜单、图标状态机、`Backend` 启停、`--selftest` |
| `icons.py` | 用 Pillow 绘制 1024px 图标，导出多尺寸 ICO 与预览图 |
| `web/index.html` | 单文件前端：每 5 秒 `fetch /api/status` 渲染，含隐私开关 |

## 本地数据

```
local/                 # 已 gitignore
├─ config.json         # 设备地址 / 端口 / adb 路径
├─ settings.json       # mask_sensitive / refresh_seconds
├─ logs/               # tray.log / selftest.log / tray_error.log
└─ shots/              # 截图产物
```

写入路径全部经 `config.local_dir()` 等函数计算：冻结后位于 exe 同目录，源码运行位于仓库根目录。
不存在任何写入系统目录的行为。

## 线程模型

- **主线程**：`pystray.Icon.run()` 的 Windows 消息循环（托盘必须跑在主线程）
- **服务线程**：`ThreadingHTTPServer.serve_forever()`，每个请求一个线程
- **轮询线程**：每 `poll_seconds` 请求一次 `/api/ping`，更新图标与 tooltip
- **自启动清单**：`dumpsys package` 输出可达数 MB，首次访问时起后台线程加载，5 分钟缓存；未命中先返回空数组，避免首屏卡住

## 数据采集要点

- 心跳用 `adb shell echo ok`（毫秒级），带 4 秒缓存，避免轮询压垮 adb
- 服务清单来自 `dumpsys activity services`，按 `ServiceRecord` 行提取 `pkg/svc`
- 自启动清单解析 `dumpsys package` 中 `BOOT_COMPLETED` 后的缩进块
- 画面流为 `adb exec-out screencap -p` 的 PNG 逐帧 multipart 推送；用非阻塞锁限制单路

## 打包

PyInstaller onefile + noconsole：

```
pyinstaller --onefile --noconsole --name TrayTVAdmin \
  --icon assets/icons/tv_on.ico \
  --add-data "src/tvremote/web;web" \
  --paths src \
  --hidden-import pystray._win32 --hidden-import pystray._base \
  --hidden-import pystray._util.win32 \
  main.py
```

- `pystray` 的后端是按平台名动态导入的，静态分析扫不到，必须显式 `--hidden-import`
- `web/index.html` 通过 `--add-data` 打进包内，运行时用 `sys._MEIPASS` 定位
- 运行期文件（`config.json`、`tray.log`、截图）写在 exe 同目录，不写入系统目录
