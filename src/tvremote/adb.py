# -*- coding: utf-8 -*-
"""ADB 薄封装：定位可执行文件、执行命令、返回原始字节。"""
from __future__ import annotations

import os
import shutil
import subprocess

CANDIDATES = (
    os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
    os.path.expandvars(r"%ANDROID_HOME%\platform-tools\adb.exe"),
    os.path.expandvars(r"%ANDROID_SDK_ROOT%\platform-tools\adb.exe"),
    r"C:\platform-tools\adb.exe",
)


def find_adb(explicit: str = "") -> str:
    if explicit and os.path.isfile(explicit):
        return explicit
    hit = shutil.which("adb")
    if hit:
        return hit
    for c in CANDIDATES:
        if os.path.isfile(c):
            return c
    return "adb"


class Adb:
    def __init__(self, device: str, adb_path: str = ""):
        self.device = device
        self.path = find_adb(adb_path)
        self._last_connect = 0.0

    def _exec(self, args: list[str], timeout: int = 20) -> tuple[bytes, str, int]:
        try:
            p = subprocess.run(
                [self.path, "-s", self.device] + args,
                capture_output=True,
                timeout=timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return p.stdout, p.stderr.decode("utf-8", "ignore"), p.returncode
        except subprocess.TimeoutExpired:
            return b"", "timeout", 124
        except FileNotFoundError:
            return b"", f"adb not found: {self.path}", 127
        except Exception as e:  # noqa: BLE001
            return b"", str(e), 1

    def run(self, args: list[str], timeout: int = 20) -> tuple[bytes, str, int]:
        """执行 adb 命令；设备掉线时自动 connect 后重试一次（容器/远程场景必需）。"""
        out, err, rc = self._exec(args, timeout)
        if rc != 0:
            low = err.lower()
            if any(k in low for k in ("not found", "offline", "no devices", "unauthorized", "cannot connect", "closed")):
                self.connect()
                out, err, rc = self._exec(args, timeout)
        return out, err, rc

    def shell(self, cmd: str, timeout: int = 20) -> str:
        out, _err, _rc = self.run(["shell", cmd], timeout=timeout)
        return out.decode("utf-8", "ignore").strip()

    def connect(self, timeout: int = 8) -> bool:
        """按需连接 TCP 设备，5 秒内不重复尝试。"""
        import time

        now = time.time()
        if now - self._last_connect < 5:
            return False
        self._last_connect = now
        try:
            subprocess.run(
                [self.path, "connect", self.device],
                capture_output=True,
                timeout=timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return True
        except Exception:  # noqa: BLE001
            return False
