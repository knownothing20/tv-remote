# -*- coding: utf-8 -*-
"""无界面模式：只跑 Web 服务，供 Docker / NAS / 服务器部署使用。

与托盘版共用同一套采集与面板，区别仅在于没有托盘图标、由外部进程管理生命周期。
"""
from __future__ import annotations

import argparse
import sys

from . import __version__, server
from .config import load_config


def main(argv=None):
    argv = [a for a in (sys.argv[1:] if argv is None else argv) if a != "--headless"]

    parser = argparse.ArgumentParser(prog="tvremote-headless", description="电视管理后台 · 无界面服务")
    parser.add_argument("--device", help="电视 ADB 地址，如 192.168.1.10:5555")
    parser.add_argument("--host", help="绑定地址，容器内用 0.0.0.0")
    parser.add_argument("--port", type=int, help="端口（默认 8777）")
    args = parser.parse_args(argv)

    cfg = load_config()
    if args.device:
        cfg.device = args.device
    if args.host:
        cfg.host = args.host
    if args.port:
        cfg.port = args.port

    server.init(cfg)
    server.warmup()
    print(
        f"tv-remote v{__version__} · http://{cfg.host}:{cfg.port} · device {cfg.device}"
        + (" · token 已启用" if cfg.token else ""),
        flush=True,
    )
    server.serve(cfg.port, cfg.host)
