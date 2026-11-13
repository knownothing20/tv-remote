# -*- coding: utf-8 -*-
"""托盘应用：右键菜单、双态图标、服务生命周期、无界面自检。"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from urllib.parse import quote

from . import __version__, icons, privacy, server
from .config import Config, load_config, load_devices, logs_dir, set_active_device


def log(msg: str, name: str = "tray.log"):
    try:
        with open(os.path.join(logs_dir(), name), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + privacy.mask_text(msg) + "\n")
    except Exception:
        pass


def port_open(port: int, timeout: float = 0.4) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except Exception:
        return False
    finally:
        s.close()


def device_online(url: str, token: str = "", timeout: float = 6.0) -> bool:
    """心跳判定：必须带上访问口令，否则服务端返回 401 会被误判为离线。"""
    query = ("?token=" + quote(token)) if token else ""
    try:
        with urllib.request.urlopen(url + "/api/ping" + query, timeout=timeout) as r:
            return bool(json.loads(r.read().decode("utf-8")).get("tv"))
    except Exception:
        return False


class Backend:
    """本地 HTTP 服务的启停控制（与托盘同生命周期）。"""

    def __init__(self, config: Config):
        self.cfg = config
        self.srv = None

    def start(self) -> bool:
        if port_open(self.cfg.port):
            return True
        server.init(self.cfg)
        server.warmup()
        try:
            self.srv = server.make_server(self.cfg.port)
            threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        except Exception as e:  # noqa: BLE001
            log("backend start failed: %r" % e)
            return False
        for _ in range(40):
            if port_open(self.cfg.port):
                return True
            time.sleep(0.15)
        return False

    def stop(self):
        if self.srv is not None:
            try:
                self.srv.shutdown()
                self.srv.server_close()
            except Exception:
                pass
            self.srv = None


def copy_clip(text: str) -> bool:
    try:
        subprocess.run(["clip"], input=text.encode("utf-8"), check=False,
                       creationflags=0x08000000)
        return True
    except Exception:
        return False


def dashboard_url(config: Config, extra: str = "") -> str:
    """面板地址：监听 0.0.0.0 时用局域网 IP，并自动附带访问口令。"""
    url = config.public_url + "/"
    if config.token:
        url += "?token=" + quote(config.token)
        if extra:
            url += "&" + extra
    elif extra:
        url += "?" + extra
    return url


def device_menu_items(switch_to, open_panel):
    """构建设备子菜单。

    注意：pystray 的 MenuItem 回调只接受 0~2 个位置参数，
    因此每项都通过闭包工厂生成（不能写成带默认值的第三个参数）。
    供托盘与自检共用，便于自检捕获回调签名错误。
    """
    from pystray import Menu, MenuItem

    try:
        data = load_devices()
    except Exception:
        return [MenuItem("（读取设备列表失败）", None, enabled=False)]

    def make(dev):
        dev_id = dev["id"]
        label = dev.get("name") or dev["device"]

        def handler(icon, item):
            switch_to(icon, dev_id)

        def is_checked(item):
            return load_devices()["active"] == dev_id

        return MenuItem(label, handler, radio=True, checked=is_checked)

    items = [make(dev) for dev in data["items"][:10]]
    items.append(Menu.SEPARATOR)
    items.append(MenuItem("添加 / 管理设备…", lambda icon, item: open_panel()))
    return items


def run_tray(config: Config):
    import pystray
    from pystray import Menu, MenuItem

    on_img, off_img = icons.tray_image(True), icons.tray_image(False)
    backend = Backend(config)
    backend.start()

    def open_dash(icon=None, item=None):
        webbrowser.open(dashboard_url(config))

    def do_copy(icon=None, item=None):
        copy_clip(dashboard_url(config))

    def do_restart(icon=None, item=None):
        backend.stop()
        time.sleep(0.6)
        backend.start()

    def do_quit(icon=None, item=None):
        backend.stop()
        icon.visible = False
        icon.stop()

    def switch_to(icon, device_id):
        target = set_active_device(device_id)
        if target:
            server.set_device(target["device"], target.get("adb") or "")
            log(f"switch device -> {target.get('name') or target['device']}")
            icon.update_menu()
            icon.notify(f"已切换到 {target.get('name') or target['device']}")

    menu = Menu(
        MenuItem("打开管理后台", open_dash, default=True),
        MenuItem("设备", Menu(*device_menu_items(
            switch_to, lambda: webbrowser.open(dashboard_url(config, "manage=1"))))),
        MenuItem("复制访问地址", do_copy),
        Menu.SEPARATOR,
        MenuItem("重启服务", do_restart),
        Menu.SEPARATOR,
        MenuItem("退出（关闭服务）", do_quit),
    )

    icon = pystray.Icon("tvremote", off_img, "电视管理后台 · 检测中", menu)
    interval = max(2, int(config.poll_seconds))

    def poll():
        while True:
            try:
                online = device_online(config.url, config.token)
                icon.icon = on_img if online else off_img
                icon.title = f"电视管理后台 v{__version__} · " + ("已连接" if online else "未连接")
            except Exception as e:  # noqa: BLE001
                log("poll error: %r" % e)
            time.sleep(interval)

    threading.Thread(target=poll, daemon=True).start()
    icon.run()


def selftest(config: Config) -> dict:
    """无界面自检：验证服务、设备连通、托盘后端可加载。"""
    result: dict = {"version": __version__, "device": privacy.mask_device(config.device)}
    backend = Backend(config)
    result["backend_started"] = backend.start()
    result["port_open"] = port_open(config.port)
    result["device_online"] = device_online(config.url, config.token, timeout=15)
    try:
        import pystray
        from pystray import Menu, MenuItem

        probe = pystray.Icon("tvremote_selftest", icons.tray_image(True), "selftest",
                             Menu(MenuItem("打开管理后台", lambda: None)))
        result["tray_backend_ok"] = True
        result["tray_backend"] = type(probe).__module__
        del probe

        # 真实菜单（含设备子菜单）也要能构建，避免回调签名类错误漏检
        probe_menu = Menu(*device_menu_items(lambda icon, dev_id: None, lambda: None))
        result["tray_menu_ok"] = probe_menu is not None
    except Exception as e:  # noqa: BLE001
        result["tray_backend_ok"] = False
        result["tray_error"] = repr(e)
    backend.stop()
    with open(os.path.join(logs_dir(), "selftest.log"), "w", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tvremote", description="电视管理后台 · 托盘版")
    parser.add_argument("--device", help="电视 ADB 地址，如 192.168.1.10:5555")
    parser.add_argument("--port", type=int, help="本地 Web 端口（默认 8777）")
    parser.add_argument("--selftest", action="store_true", help="无界面自检并退出")
    parser.add_argument("--export-icons", metavar="DIR", help="导出图标到指定目录后退出")
    args = parser.parse_args(argv)

    if args.export_icons:
        print("\n".join(icons.export_icons(args.export_icons)))
        return

    config = load_config()
    if args.device:
        config.device = args.device
    if args.port:
        config.port = args.port

    if args.selftest:
        selftest(config)
        return

    try:
        run_tray(config)
    except Exception:
        with open(os.path.join(logs_dir(), "tray_error.log"), "w", encoding="utf-8") as f:
            f.write(privacy.mask_text(traceback.format_exc()))
        raise
