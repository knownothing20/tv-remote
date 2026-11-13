# -*- coding: utf-8 -*-
"""本地 Web 管理面板：ADB 数据采集 + REST API + MJPEG 实时画面。"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import __version__, adapters, privacy
from .adb import Adb
from .config import (
    Config,
    load_config,
    load_devices,
    load_settings,
    local_dir,
    remove_device,
    resource_path,
    set_active_device,
    shots_dir,
    update_settings,
    upsert_device,
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
    try:  # 供一键更新脚本读取本地版本
        with open(os.path.join(local_dir(), "version.txt"), "w", encoding="utf-8") as f:
            f.write(__version__ + "\n")
    except Exception:
        pass
    return _cfg


def cfg() -> Config:
    if _cfg is None:
        init()
    return _cfg  # type: ignore[return-value]


def adb() -> Adb:
    if _adb is None:
        init()
    return _adb  # type: ignore[return-value]


def set_device(device: str, adb_path: str = "") -> None:
    """运行时切换目标设备（面板/托盘切换时调用）。"""
    global _adb
    c = cfg()
    c.device = device
    if adb_path:
        c.adb = adb_path
    _adb = Adb(device, c.adb)
    _cache.clear()
    _ping["t"], _ping["v"] = 0.0, False


def devices_payload() -> dict:
    """设备列表（按隐私设置决定是否打码地址）。"""
    data = load_devices()
    mask = load_settings().mask_sensitive
    items = []
    for item in data["items"]:
        items.append({
            "id": item["id"],
            "name": item.get("name") or item["device"],
            "device": privacy.mask_device(item["device"]) if mask else item["device"],
            "device_raw": "" if mask else item["device"],
        })
    return {"active": data["active"], "items": items, "masked": mask}


def handle_device_action(body: dict) -> dict:
    action = (body.get("action") or "").strip()
    if action == "select":
        target = set_active_device(body.get("id", ""))
        if not target:
            return {"ok": False, "msg": "设备不存在"}
        set_device(target["device"], target.get("adb") or "")
        return {"ok": True, "msg": "已切换", "devices": devices_payload()}
    if action in ("add", "update"):
        device = (body.get("device") or "").strip()
        if not device:
            return {"ok": False, "msg": "请填写设备地址"}
        item = upsert_device(body.get("id") or None, body.get("name") or "", device,
                             body.get("adb") or "")
        if action == "add" and not body.get("id"):
            set_active_device(item["id"])
            set_device(item["device"], item.get("adb") or "")
        return {"ok": True, "msg": "已保存", "devices": devices_payload()}
    if action == "remove":
        remove_device(body.get("id", ""))
        cur = cfg()
        from .config import active_device

        act = active_device()
        set_device(act["device"], act.get("adb") or "")
        return {"ok": True, "msg": "已删除", "devices": devices_payload()}
    return {"ok": False, "msg": "未知操作"}


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


BLOCKED_PACKAGES = {
    "android",
    "com.android.systemui",
    "com.android.settings",
    "com.android.packageinstaller",
    "com.android.permissioncontroller",
    "com.android.providers.settings",
    "com.google.android.gms",
    "com.tcl.systemserver",
}

_APP_NAME_RE = re.compile(r"^[A-Za-z0-9_.]+$")


def get_apps(scope: str = "third", query: str = "") -> list:
    """已安装应用列表（含版本号与是否系统应用），30 秒缓存。"""

    def _collect() -> dict:
        third = set(re.findall(r"package:([\w.]+)", sh("pm list packages -3", timeout=30)))
        raw = sh("pm list packages --show-versioncode", timeout=40)
        items, seen = [], set()
        for line in raw.splitlines():
            m = re.match(r"package:([\w.]+)(?:\s+versionCode:(\d+))?", line.strip())
            if not m:
                continue
            pkg = m.group(1)
            if pkg in seen:
                continue
            seen.add(pkg)
            items.append({
                "pkg": pkg,
                "versionCode": m.group(2) or "",
                "system": pkg not in third,
                "blocked": pkg in BLOCKED_PACKAGES,
            })
        items.sort(key=lambda a: a["pkg"])
        return {"items": items}

    items = cached("apps", 30, _collect)["items"]
    if scope == "third":
        items = [a for a in items if not a["system"]]
    if query:
        q = query.lower()
        items = [a for a in items if q in a["pkg"].lower()]
    return items


def do_app_action(cmd: str, pkg: str) -> dict:
    pkg = (pkg or "").strip()
    if not pkg or not _APP_NAME_RE.match(pkg):
        return {"ok": False, "msg": "包名非法"}

    if cmd in {"uninstall", "disable", "clear"} and pkg in BLOCKED_PACKAGES:
        return {"ok": False, "msg": "受保护的系统组件，已拒绝执行"}

    commands = {
        "open": ("monkey -p %s 1", "已尝试启动"),
        "stop": ("am force-stop %s", "已停止"),
        "disable": ("pm disable-user --user 0 %s", "已停用"),
        "enable": ("pm enable %s", "已启用"),
        "clear": ("pm clear %s", "已清除数据"),
        "uninstall": ("pm uninstall --user 0 %s", "已卸载"),
    }
    if cmd not in commands:
        return {"ok": False, "msg": "未知操作"}

    tpl, label = commands[cmd]
    out = sh(tpl % pkg, timeout=40)
    installed = pkg in sh(f"pm list packages {pkg}", timeout=15)
    with _cache_lock:
        _cache.pop("apps", None)
    return {
        "ok": ("Exception" not in out and "Error" not in out),
        "msg": f"{label}：{out[:120] or 'ok'}",
        "installed": installed,
    }


def _ver_tuple(version: str) -> tuple:
    parts = re.findall(r"\d+", version or "")[:3]
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def get_update_info() -> dict:
    """查询 GitHub Releases 最新版本；关闭检查时直接返回 disabled。"""
    info = {
        "current": __version__,
        "enabled": load_settings().check_updates,
        "latest": "",
        "has_update": False,
        "url": "",
        "error": "",
    }
    if not info["enabled"]:
        return info

    def _fetch() -> dict:
        import urllib.request

        req = urllib.request.Request(
            "https://api.github.com/repos/knownothing20/tv-remote/releases/latest",
            headers={"User-Agent": "tv-remote", "Accept": "application/vnd.github+json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return {
                "latest": (data.get("tag_name") or "").lstrip("v"),
                "url": data.get("html_url") or "",
                "published": data.get("published_at") or "",
            }
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)[:140]}

    remote = cached("update", 1800, _fetch)
    if remote.get("error"):
        info["error"] = remote["error"]
        return info
    info["latest"] = remote.get("latest", "")
    info["url"] = remote.get("url", "")
    info["has_update"] = bool(info["latest"]) and _ver_tuple(info["latest"]) > _ver_tuple(__version__)
    return info


_history: list = []
_history_lock = threading.Lock()


def _record_history(mem: dict) -> None:
    with _history_lock:
        _history.append({
            "t": int(time.time()),
            "mem": mem.get("pct", 0),
            "avail": mem.get("avail_mb", 0),
        })
        del _history[:-180]


def get_history() -> list:
    with _history_lock:
        return list(_history)


def adapter_payload() -> dict:
    """当前设备命中的机型适配器（包名 -> 中文名 / 角色 / 策略）。"""
    return cached("adapter", 600, lambda: adapters.payload(get_props()))


def get_whitelist() -> list:
    return [l.split(",")[1] for l in sh("cmd deviceidle whitelist", timeout=10).splitlines() if l.count(",") >= 1]


_ping = {"t": 0.0, "v": False}
_online_state = {"last": None}
_launch_guard = {"t": 0.0}
RECEIVER_PKG = "com.weenas.castbay"
CAST_PORT = 7000


def _foreground_pkg() -> str:
    m = re.search(r"u0 ([\w.]+)/", sh("dumpsys activity activities | grep -m1 mResumedActivity", timeout=10))
    return m.group(1) if m else ""


def _media_playing() -> bool:
    """检测是否有媒体正在播放，避免打断观看。"""
    out = sh("dumpsys media_session | grep -m1 -E 'state=PlaybackState \\{state=3'", timeout=12)
    return bool(out.strip())


def _cast_connected() -> bool:
    """接收端端口上是否已有已建立的连接（说明 iPad 已经开始投屏）。"""
    out = sh(f"netstat -an 2>/dev/null | grep ':{CAST_PORT} ' | grep -i established", timeout=8)
    return bool(out.strip())


_foreground_guard = {"t": 0.0}


def _ensure_foreground_on_cast() -> None:
    """投屏期间把接收端切到前台。

    接收端退到后台后，渲染用的 Surface 会被系统销毁：音频仍能播放，
    但视频没有可绘制目标，表现就是「有声音、画面全黑」。
    """
    now = time.time()
    if now - _foreground_guard["t"] < 8:
        return
    try:
        if not load_settings().foreground_on_cast:
            return
        if _foreground_pkg() == RECEIVER_PKG:
            return
        if not _cast_connected():
            return
    except Exception:
        return
    _foreground_guard["t"] = now
    try:
        sh(f"monkey -p {RECEIVER_PKG} 1", timeout=15)
    except Exception:
        pass


def _maybe_launch_receiver() -> None:
    """按设置确保投屏接收端在运行；silent_launch 时拉起后立刻退回原画面。"""
    now = time.time()
    if now - _launch_guard["t"] < 60:      # 最多每分钟尝试一次，避免与用户手动关闭打架
        return
    try:
        settings = load_settings()
        if not settings.auto_launch_receiver:
            return
        if sh(f"pidof {RECEIVER_PKG}", timeout=6):
            return
        if _media_playing():
            return
    except Exception:
        return

    _launch_guard["t"] = now
    silent = getattr(settings, "silent_launch", True)
    prev_pkg = _foreground_pkg() if silent else ""

    def _go():
        try:
            sh(f"monkey -p {RECEIVER_PKG} 1", timeout=20)
            if not silent:
                return
            time.sleep(1.4)               # 等接收端起来（广播/端口就绪）
            if prev_pkg and prev_pkg != RECEIVER_PKG and not prev_pkg.startswith("com.tcl.cyberui"):
                sh(f"monkey -p {prev_pkg} 1", timeout=15)   # 回到原来的应用
            else:
                sh("input keyevent 3", timeout=10)          # 回桌面
        except Exception:
            pass

    threading.Thread(target=_go, daemon=True).start()


def tv_online() -> bool:
    now = time.time()
    if now - _ping["t"] < 4:
        return _ping["v"]
    out, _err, _rc = adb().run(["shell", "echo ok"], timeout=3)
    ok = b"ok" in out
    _ping["t"], _ping["v"] = now, ok
    if ok:
        _maybe_launch_receiver()
    _online_state["last"] = ok
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
    st["adapter"] = adapter_payload().get("matched", "")
    st["mem"] = get_mem()
    _record_history(st["mem"])
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

    def _static(self, name: str, ctype: str):
        try:
            with open(resource_path(os.path.join("web", name)), "rb") as f:
                self._send(200, f.read(), ctype)
        except Exception:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def _unauthorized(self):
        """401：首页给可读的提示页，API 返回 JSON。"""
        if urlparse(self.path).path in ("", "/"):
            page = (
                "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
                "<title>需要访问口令</title><meta name='viewport' content='width=device-width,initial-scale=1'>"
                "</head><body style=\"font-family:-apple-system,'Segoe UI','Microsoft YaHei',sans-serif;"
                "background:#0d1117;color:#e6edf3;padding:48px;line-height:1.7\">"
                "<h2 style='font-weight:500'>需要访问口令</h2>"
                "<p style='color:#8b949e'>已在 <code>local/config.json</code> 启用 <code>token</code>，"
                "请在地址后加上口令：</p>"
                "<pre style='background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px'>"
                "http://127.0.0.1:8777/?token=你的口令</pre>"
                "<p style='color:#8b949e'>托盘右键「复制访问地址」会自动带上口令。</p>"
                "</body></html>"
            )
            self._send(401, page, "text/html; charset=utf-8")
        else:
            self._send(401, json.dumps({"error": "unauthorized"}, ensure_ascii=False))

    def do_GET(self):
        if not self._authorized():
            self._unauthorized()
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
        elif path == "/api/devices":
            self._send(200, json.dumps(devices_payload(), ensure_ascii=False))
        elif path == "/api/apps":
            qs = parse_qs(urlparse(self.path).query)
            scope = qs.get("scope", ["third"])[0] or "third"
            query = qs.get("q", [""])[0]
            self._send(200, json.dumps({"items": get_apps(scope, query)}, ensure_ascii=False))
        elif path == "/api/adapter":
            self._send(200, json.dumps(adapter_payload(), ensure_ascii=False))
        elif path == "/api/update":
            self._send(200, json.dumps(get_update_info(), ensure_ascii=False))
        elif path == "/api/history":
            self._send(200, json.dumps({"items": get_history()}, ensure_ascii=False))
        elif path == "/manifest.webmanifest":
            self._static("manifest.webmanifest", "application/manifest+json; charset=utf-8")
        elif path == "/sw.js":
            self._static("sw.js", "application/javascript; charset=utf-8")
        elif path == "/icon-192.png":
            self._static("icon-192.png", "image/png")
        elif path == "/icon-512.png":
            self._static("icon-512.png", "image/png")
        elif path == "/favicon.ico":
            self._static("icon-192.png", "image/png")
        elif path == "/api/settings":
            s = load_settings()
            self._send(200, json.dumps({
                "mask_sensitive": s.mask_sensitive,
                "refresh_seconds": s.refresh_seconds,
                "check_updates": s.check_updates,
                "auto_launch_receiver": s.auto_launch_receiver,
                "silent_launch": s.silent_launch,
                "foreground_on_cast": s.foreground_on_cast,
            }, ensure_ascii=False))
        elif path == "/api/screen":
            self.stream_screen()
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if not self._authorized():
            self._unauthorized()
            return
        path = urlparse(self.path).path
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            body = {}

        if path == "/api/devices":
            self._send(200, json.dumps(handle_device_action(body), ensure_ascii=False))
            return

        if path == "/api/app":
            self._send(200, json.dumps(
                do_app_action(body.get("cmd", ""), body.get("pkg", "")), ensure_ascii=False))
            return

        if path == "/api/settings":
            s = update_settings(
                mask_sensitive=body.get("mask_sensitive"),
                refresh_seconds=body.get("refresh_seconds"),
                check_updates=body.get("check_updates"),
                auto_launch_receiver=body.get("auto_launch_receiver"),
                silent_launch=body.get("silent_launch"),
                foreground_on_cast=body.get("foreground_on_cast"),
            )
            with _cache_lock:
                _cache.pop("update", None)
            self._send(200, json.dumps({
                "ok": True,
                "mask_sensitive": s.mask_sensitive,
                "refresh_seconds": s.refresh_seconds,
                "check_updates": s.check_updates,
                "auto_launch_receiver": s.auto_launch_receiver,
                "silent_launch": s.silent_launch,
                "foreground_on_cast": s.foreground_on_cast,
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
    start_watchdog()
    bind = host or cfg_.host
    srv = ThreadingHTTPServer((bind, port or cfg_.port), Handler)
    srv.daemon_threads = True
    return srv


_watchdog_started = False


def start_watchdog() -> None:
    """后台守护：心跳 + 投屏前台切换。托盘与 headless 模式共用。"""
    global _watchdog_started
    if _watchdog_started:
        return
    _watchdog_started = True
    interval = max(3, int(cfg().poll_seconds))

    def loop():
        while True:
            try:
                tv_online()
                _ensure_foreground_on_cast()
            except Exception:
                pass
            time.sleep(interval)

    threading.Thread(target=loop, daemon=True).start()


def serve(port: int | None = None, host: str | None = None):
    make_server(port, host).serve_forever()
