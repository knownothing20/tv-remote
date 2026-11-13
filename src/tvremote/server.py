# -*- coding: utf-8 -*-
"""本地 Web 管理面板：ADB 数据采集 + REST API + MJPEG 实时画面。"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import __version__, privacy
from .adb import Adb
from .config import (
    Config,
    load_config,
    load_settings,
    resource_path,
    shots_dir,
    update_settings,
)

_cfg: Config | None = None
_adb: Adb | None = None
_cache: dict = {}
_cache_lock = threading.Lock()
_screen_lock = threading.Lock()
_boot_loading = False
_html_cache: str | None = None


def init(config: Config | None = None) -> Config:
    """初始化全局配置与 ADB 客户端（幂等）。"""
    global _cfg, _adb, _cache
    _cfg = config or load_config()
    _adb = Adb(_cfg.device, _cfg.adb)
    _cache = {}
    return _cfg


def cfg() -> Config:
    if _cfg is None:
        init()
    return _cfg  # type: ignore[return-value]


def adb() -> Adb:
    if _adb is None:
        init()
    return _adb  # type: ignore[return-value]


def sh(cmd: str, timeout: int = 20) -> str:
    return adb().shell(cmd, timeout=timeout)


def cached(key: str, ttl: float, fn):
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    val = fn()
    with _cache_lock:
        _cache[key] = (now, val)
    return val


# ------------------------------------------------------------------ collectors
def get_props() -> dict:
    props = [
        "ro.product.model", "ro.product.brand", "ro.build.version.release",
        "ro.build.version.sdk", "ro.product.cpu.abilist", "ro.serialno",
        "ro.build.display.id", "ro.product.board", "ro.hardware",
        "persist.sys.timezone", "ro.build.date",
    ]
    vals = sh("; ".join(f"getprop {p}" for p in props)).splitlines()
    vals += [""] * (len(props) - len(vals))
    return {p: v.strip() for p, v in zip(props, vals)}


def get_mem() -> dict:
    d = {}
    for line in sh("cat /proc/meminfo").splitlines():
        m = re.match(r"(\w+):\s+(\d+)", line)
        if m:
            d[m.group(1)] = int(m.group(2))
    total = d.get("MemTotal", 0)
    avail = d.get("MemAvailable", d.get("MemFree", 0))
    return {
        "total_mb": round(total / 1024),
        "avail_mb": round(avail / 1024),
        "used_mb": round((total - avail) / 1024),
        "pct": round((total - avail) / total * 100) if total else 0,
    }


def get_uptime() -> str:
    txt = sh("cat /proc/uptime")
    try:
        secs = float(txt.split()[0])
    except Exception:
        return ""
    days, rem = divmod(int(secs), 86400)
    hours, rem = divmod(rem, 3600)
    return f"{days}天 {hours}小时 {rem // 60}分"


def get_storage() -> list:
    rows = []
    for line in sh("df -k /data /storage/emulated").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 6 and parts[0].startswith("/"):
            total, used = int(parts[1]), int(parts[2])
            rows.append({
                "mount": parts[5],
                "total_gb": round(total / 1024 / 1024, 1),
                "used_gb": round(used / 1024 / 1024, 1),
                "avail_gb": round(int(parts[3]) / 1024 / 1024, 1),
                "pct": round(used / total * 100) if total else 0,
            })
    return rows


def get_network() -> dict:
    ip = ""
    m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", sh("ip -4 addr show wlan0"))
    if m:
        ip = m.group(1)
    wifi = {"ssid": "", "rssi": "", "speed": ""}
    status = sh("cmd wifi status", timeout=10)
    m = re.search(r'SSID:\s*"?([^",]+)"?', status)
    if m:
        wifi["ssid"] = m.group(1).strip()
    m = re.search(r"RSSI:\s*(-?\d+)", status)
    if m:
        wifi["rssi"] = m.group(1) + " dBm"
    m = re.search(r"Link speed:\s*([^\n,]+)", status)
    if m:
        wifi["speed"] = m.group(1).strip()
    if not wifi["ssid"]:
        dump = sh("dumpsys wifi | grep -m3 -E 'mWifiInfo|RSSI'", timeout=15)
        m = re.search(r'SSID: "([^"]+)"', dump)
        if m:
            wifi["ssid"] = m.group(1)
        if not wifi["rssi"]:
            m = re.search(r"RSSI:\s*(-?\d+)", dump)
            if m:
                wifi["rssi"] = m.group(1) + " dBm"
    return {"ip": ip, "wifi": wifi}


def get_screen_info() -> dict:
    return {
        "size": sh("wm size").replace("Physical size:", "").strip(),
        "density": sh("wm density").replace("Physical density:", "").strip(),
    }


def get_foreground() -> dict:
    m = re.search(r"u0 ([\w.]+)/([\w.$]+)", sh("dumpsys activity activities | grep -m1 mResumedActivity"))
    return {"package": m.group(1), "activity": m.group(2)} if m else {"package": "", "activity": ""}


def get_processes(limit: int = 12) -> list:
    out = sh(f"ps -A -o PID,RSS,NAME | sort -k2 -nr | head -{limit + 1}")
    rows = []
    for line in out.splitlines()[1:]:
        parts = line.split(None, 2)
        if len(parts) == 3:
            try:
                rows.append({"pid": parts[0], "rss_mb": round(int(parts[1]) / 1024, 1), "name": parts[2]})
            except ValueError:
                pass
    return rows[:limit]


def get_services(limit: int = 40) -> list:
    rows, seen = [], set()
    for line in sh("dumpsys activity services", timeout=25).splitlines():
        m = re.search(r"(?:u0|u10)\s+([a-zA-Z][\w.]*)/([\w.$]+)", line)
        if m and "ServiceRecord" in line:
            key = m.group(1) + "/" + m.group(2)
            if key not in seen:
                seen.add(key)
                rows.append({"pkg": m.group(1), "svc": m.group(2)})
    return rows[:limit]


def get_boot_receivers() -> list:
    """解析 dumpsys package，找出监听 BOOT_COMPLETED 的应用（较重，缓存 5 分钟）。"""
    out, _err, _rc = adb().run(["shell", "dumpsys package"], timeout=120)
    lines = out.decode("utf-8", "ignore").splitlines()
    pkgs = set()
    for i, line in enumerate(lines):
        if "android.intent.action.BOOT_COMPLETED" not in line:
            continue
        indent = len(line) - len(line.lstrip())
        j = i + 1
        while j < len(lines):
            s = lines[j]
            if not s.strip():
                j += 1
                continue
            if len(s) - len(s.lstrip()) <= indent:
                break
            for m in re.finditer(r"([a-zA-Z][\w.]+)/(\.[\w.$]+)", s):
                pkgs.add(m.group(1))
            j += 1
    return sorted(pkgs)


def get_boot_cached() -> list:
    """非阻塞：命中缓存直接返回，否则后台加载，本次返回空。"""
    with _cache_lock:
        hit = _cache.get("boot")
        if hit and time.time() - hit[0] < 300:
            return hit[1]
    threading.Thread(target=_load_boot, daemon=True).start()
    return []


def _load_boot():
    global _boot_loading
    if _boot_loading:
        return
    _boot_loading = True
    try:
        data = get_boot_receivers()
    except Exception:
        data = []
    with _cache_lock:
        _cache["boot"] = (time.time(), data)
    _boot_loading = False


def warmup():
    """启动时后台预热较重的采集项（自启动清单）。"""
    threading.Thread(target=_load_boot, daemon=True).start()


def get_whitelist() -> list:
    return [l.split(",")[1] for l in sh("cmd deviceidle whitelist", timeout=10).splitlines() if l.count(",") >= 1]


_ping = {"t": 0.0, "v": False}


def tv_online() -> bool:
    now = time.time()
    if now - _ping["t"] < 4:
        return _ping["v"]
    out, _err, _rc = adb().run(["shell", "echo ok"], timeout=3)
    ok = b"ok" in out
    _ping["t"], _ping["v"] = now, ok
    return ok


def get_castbay() -> dict:
    """可选集成：映湾 CastBay（AirPlay 接收端）状态。"""
    pid = sh("pidof com.weenas.castbay").strip()
    return {
        "installed": bool(sh("pm list packages com.weenas.castbay").strip()),
        "running": bool(pid),
        "pid": pid,
        "port": "7000 LISTEN" if "LISTEN" in sh("netstat -an | grep ':7000'") else "",
    }


def collect_status() -> dict:
    mask = load_settings().mask_sensitive
    st = {
        "ts": time.strftime("%H:%M:%S"),
        "online": tv_online(),
        "device": cfg().device,
        "version": __version__,
    }
    if not st["online"]:
        return privacy.apply_status(st, mask)
    st["props"] = get_props()
    st["mem"] = get_mem()
    st["uptime"] = get_uptime()
    st["storage"] = get_storage()
    st["net"] = get_network()
    st["screen"] = get_screen_info()
    st["foreground"] = get_foreground()
    st["processes"] = get_processes()
    st["services"] = cached("services", 8, get_services)
    st["boot"] = get_boot_cached()
    st["whitelist"] = get_whitelist()
    st["castbay"] = get_castbay()
    return privacy.apply_status(st, mask)


# ------------------------------------------------------------------- actions
def do_action(cmd: str) -> dict:
    if cmd == "castbay":
        sh("monkey -p com.weenas.castbay 1", timeout=15)
        time.sleep(1.5)
        return {"ok": True, "msg": "已启动映湾"}
    if cmd == "home":
        sh("input keyevent 3", timeout=10)
        return {"ok": True, "msg": "已回到桌面"}
    if cmd == "back":
        sh("input keyevent 4", timeout=10)
        return {"ok": True, "msg": "已发送返回键"}
    if cmd == "whitelist":
        return {"ok": True, "msg": sh("cmd deviceidle whitelist +com.weenas.castbay", timeout=10) or "已加入白名单"}
    if cmd == "screenshot":
        data, _err, _rc = adb().run(["exec-out", "screencap", "-p"], timeout=25)
        path = os.path.join(shots_dir(), time.strftime("tv_shot_%Y%m%d_%H%M%S.png"))
        with open(path, "wb") as f:
            f.write(data)
        return {"ok": bool(data), "msg": "已保存截图", "path": path}
    return {"ok": False, "msg": "未知操作"}


def load_html() -> str:
    global _html_cache
    if _html_cache is None:
        try:
            with open(resource_path(os.path.join("web", "index.html")), encoding="utf-8") as f:
                _html_cache = f.read()
        except Exception:
            _html_cache = "<h1>web/index.html 缺失</h1>"
    return _html_cache


# ---------------------------------------------------------------- http layer
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # 静默访问日志
        pass

    def _send(self, code: int, body, ctype: str = "application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _authorized(self) -> bool:
        """未配置 token 时不做校验；配置后支持 ?token= 或 X-Auth-Token。"""
        token = cfg().token
        if not token:
            return True
        if self.headers.get("X-Auth-Token") == token:
            return True
        from urllib.parse import parse_qs

        return parse_qs(urlparse(self.path).query).get("token", [""])[0] == token

    def do_GET(self):
        if not self._authorized():
            self._send(401, json.dumps({"error": "unauthorized"}, ensure_ascii=False))
            return
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, load_html(), "text/html; charset=utf-8")
        elif path == "/api/status":
            self._send(200, json.dumps(collect_status(), ensure_ascii=False))
        elif path == "/api/ping":
            try:
                online = tv_online()
            except Exception:
                online = False
            self._send(200, json.dumps({"server": True, "tv": online}))
        elif path == "/api/settings":
            s = load_settings()
            self._send(200, json.dumps({
                "mask_sensitive": s.mask_sensitive,
                "refresh_seconds": s.refresh_seconds,
            }, ensure_ascii=False))
        elif path == "/api/screen":
            self.stream_screen()
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if not self._authorized():
            self._send(401, json.dumps({"error": "unauthorized"}, ensure_ascii=False))
            return
        path = urlparse(self.path).path
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            body = {}

        if path == "/api/settings":
            s = update_settings(
                mask_sensitive=body.get("mask_sensitive"),
                refresh_seconds=body.get("refresh_seconds"),
            )
            self._send(200, json.dumps({
                "ok": True,
                "mask_sensitive": s.mask_sensitive,
                "refresh_seconds": s.refresh_seconds,
            }, ensure_ascii=False))
            return

        if path != "/api/action":
            self._send(404, json.dumps({"error": "not found"}))
            return
        self._send(200, json.dumps(do_action(body.get("cmd", "")), ensure_ascii=False))

    def stream_screen(self):
        if not _screen_lock.acquire(blocking=False):
            self._send(429, json.dumps({"error": "另一路正在观看"}))
            return
        try:
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            while True:
                t0 = time.time()
                data, _err, _rc = adb().run(["exec-out", "screencap", "-p"], timeout=25)
                if not data.startswith(b"\x89PNG"):
                    break
                self.wfile.write(b"--frame\r\nContent-Type: image/png\r\n")
                self.wfile.write(b"Content-Length: " + str(len(data)).encode() + b"\r\n\r\n")
                self.wfile.write(data)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
                dt = time.time() - t0
                if dt < 0.35:
                    time.sleep(0.35 - dt)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            _screen_lock.release()


def make_server(port: int | None = None, host: str | None = None) -> ThreadingHTTPServer:
    cfg_ = cfg()
    bind = host or cfg_.host
    srv = ThreadingHTTPServer((bind, port or cfg_.port), Handler)
    srv.daemon_threads = True
    return srv


def serve(port: int | None = None, host: str | None = None):
    make_server(port, host).serve_forever()
