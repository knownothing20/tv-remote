# 贡献指南

## 开发环境

```bash
git clone <repo> && cd tv-remote
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python main.py --selftest     # 先用自检确认环境与设备连通
python main.py                # 托盘模式
```

需要一台开启 ADB 调试的 Android TV，且与开发机同网段：

```bash
adb connect <电视IP>:5555
adb devices
```

## 代码约定

- Python 3.10+，统一 `from __future__ import annotations`
- 只用标准库 + Pillow + pystray，避免引入重量级依赖
- 新增采集项时：函数放 `server.py`，命名 `get_xxx()`，返回可 JSON 序列化的结构；
  重操作（`dumpsys package` 这类）必须走 `cached()` 或后台线程
- 前端保持 `web/index.html` 单文件，不引入构建链

## 提交

- 一个 PR 只做一件事，附带「改动原因 + 验证方式」
- 涉及界面的改动请附截图（图标改动附 16/24/32px 实拍）
- 提交前跑一遍 `python main.py --selftest`，并在 PR 里贴上输出

## 发布

1. 更新 `src/tvremote/__init__.py` 的 `__version__` 与 `CHANGELOG.md`
2. `powershell -ExecutionPolicy Bypass -File scripts/build.ps1`
3. 打 tag（`vX.Y.Z`），推送后 CI 会构建产物
