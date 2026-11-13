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

    def run(self, args: list[str], timeout: int = 20) -> tuple[bytes, str, int]:
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

    def shell(self, cmd: str, timeout: int = 20) -> str:
        out, _err, _rc = self.run(["shell", cmd], timeout=timeout)
        return out.decode("utf-8", "ignore").strip()

    def connect(self, timeout: int = 8) -> bool:
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
