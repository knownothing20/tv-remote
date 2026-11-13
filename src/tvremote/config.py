# -*- coding: utf-8 -*-
"""配置与本地数据。

所有「本地信息」集中放在 ``local/`` 目录（已 gitignore），不进入仓库：

```
local/
├─ config.json     设备地址 / 端口 / adb 路径
├─ settings.json   界面设置（隐私开关、刷新间隔）
├─ logs/           tray.log / selftest.log / tray_error.log
└─ shots/          面板「保存截图」的产物
```

加载优先级：``local/config.json`` → 兼容旧的 ``config.json`` → 内置默认值；
环境变量 ``TVREMOTE_*`` 与命令行参数可再次覆盖。
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields

DEFAULTS = {
    "device": "192.168.1.10:5555",
    "host": "127.0.0.1",
    "port": 8777,
    "adb": "",
    "token": "",
    "poll_seconds": 5,
}


def app_dir() -> str:
    """冻结后为 exe 所在目录；源码运行时为仓库根目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _ensure(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def local_dir() -> str:
    return _ensure(os.path.join(app_dir(), "local"))


def logs_dir() -> str:
    return _ensure(os.path.join(local_dir(), "logs"))


def shots_dir() -> str:
    return _ensure(os.path.join(local_dir(), "shots"))


def config_path() -> str:
    return os.path.join(local_dir(), "config.json")


def settings_path() -> str:
    return os.path.join(local_dir(), "settings.json")


def resource_path(rel: str) -> str:
    """打包后资源在 _MEIPASS，源码运行时在包目录。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, rel)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)


@dataclass
class Config:
    device: str = DEFAULTS["device"]
    host: str = DEFAULTS["host"]
    port: int = DEFAULTS["port"]
    adb: str = DEFAULTS["adb"]
    token: str = DEFAULTS["token"]
    poll_seconds: int = DEFAULTS["poll_seconds"]

    @property
    def url(self) -> str:
        host = "127.0.0.1" if self.host in ("0.0.0.0", "", "::") else self.host
        return f"http://{host}:{self.port}"

    @property
    def lan(self) -> bool:
        return self.host not in ("127.0.0.1", "localhost", "")


@dataclass
class Settings:
    """界面/行为设置，持久化到 local/settings.json。"""

    mask_sensitive: bool = True
    refresh_seconds: int = 5


def _read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_config(path: str | None = None) -> Config:
    raw = dict(DEFAULTS)

    if path is None:
        for candidate in (config_path(), os.path.join(app_dir(), "config.json")):
            if os.path.isfile(candidate):
                raw.update(_read_json(candidate))
                path = candidate
                break

    if path and os.path.isfile(path):
        raw.update(_read_json(path))

    raw["device"] = os.environ.get("TVREMOTE_DEVICE", raw["device"])
    raw["host"] = os.environ.get("TVREMOTE_HOST", raw["host"])
    raw["port"] = int(os.environ.get("TVREMOTE_PORT", raw["port"]))
    raw["adb"] = os.environ.get("TVREMOTE_ADB", raw.get("adb") or "")
    raw["token"] = os.environ.get("TVREMOTE_TOKEN", raw.get("token") or "")
    raw["poll_seconds"] = int(os.environ.get("TVREMOTE_POLL", raw["poll_seconds"]))

    allowed = {f.name for f in fields(Config)}
    cfg = Config(**{k: v for k, v in raw.items() if k in allowed})

    target = config_path()
    if not os.path.isfile(target):
        try:
            _write_json(target, asdict(cfg))
        except Exception:
            pass
    return cfg


def save_config(cfg: Config) -> str:
    path = config_path()
    _write_json(path, asdict(cfg))
    return path


def load_settings() -> Settings:
    raw = _read_json(settings_path())
    allowed = {f.name for f in fields(Settings)}
    return Settings(**{k: v for k, v in raw.items() if k in allowed})


def save_settings(settings: Settings) -> str:
    path = settings_path()
    _write_json(path, asdict(settings))
    return path


def update_settings(**changes) -> Settings:
    cur = load_settings()
    for key, value in changes.items():
        if hasattr(cur, key) and value is not None:
            setattr(cur, key, value)
    save_settings(cur)
    return cur
