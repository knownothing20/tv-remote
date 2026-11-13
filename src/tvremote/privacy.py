# -*- coding: utf-8 -*-
"""隐私脱敏。

面板与日志默认不暴露：设备 IP、序列号、Wi-Fi SSID、MAC。
由 ``local/settings.json`` 里的 ``mask_sensitive`` 开关控制（默认开启）。
"""
from __future__ import annotations


def mask_ip(ip: str) -> str:
    """192.168.1.42 → 192.168.*.*"""
    ip = (ip or "").strip()
    parts = ip.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return f"{parts[0]}.{parts[1]}.*.*"
    return "***" if ip else ip


def mask_device(addr: str) -> str:
    """192.168.1.42:5555 → 192.168.*.*:5555"""
    addr = (addr or "").strip()
    host, sep, port = addr.partition(":")
    return mask_ip(host) + (sep + port if sep else "")


def mask_serial(serial: str) -> str:
    """保留首尾各 2 位，中间打码；过短则全遮。"""
    serial = (serial or "").strip()
    if not serial:
        return serial
    if len(serial) <= 4:
        return "*" * len(serial)
    return serial[:2] + "*" * max(2, len(serial) - 4) + serial[-2:]


def mask_ssid(ssid: str) -> str:
    """Xiaomi_5G → Xi*****5G"""
    ssid = (ssid or "").strip()
    if not ssid:
        return ssid
    if len(ssid) <= 4:
        return "*" * len(ssid)
    return ssid[:2] + "*" * (len(ssid) - 4) + ssid[-2:]


def mask_mac(mac: str) -> str:
    """42:b1:f3:54:c0:62 → **:**:**:54:c0:62"""
    mac = (mac or "").strip()
    parts = mac.replace("-", ":").split(":")
    if len(parts) == 6:
        return ":".join(["**", "**", "**"] + parts[3:])
    return "***" if mac else mac


def apply_status(status: dict, enabled: bool = True) -> dict:
    """对 /api/status 的结果做脱敏（浅拷贝，不改原对象）。"""
    if not enabled or not status:
        return status

    out = dict(status)
    out["device"] = mask_device(out.get("device", ""))

    props = dict(out.get("props") or {})
    if props:
        if "ro.serialno" in props:
            props["ro.serialno"] = mask_serial(props["ro.serialno"])
        out["props"] = props

    net = dict(out.get("net") or {})
    if net:
        net["ip"] = mask_ip(net.get("ip", ""))
        wifi = dict(net.get("wifi") or {})
        if wifi:
            wifi["ssid"] = mask_ssid(wifi.get("ssid", ""))
            net["wifi"] = wifi
        out["net"] = net

    out["masked"] = True
    return out


def mask_text(text: str) -> str:
    """给日志/错误信息用的兜底脱敏：遮蔽 IPv4 与形似序列号的串。"""
    import re

    text = re.sub(r"\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b",
                  lambda m: f"{m.group(1)}.{m.group(2)}.*.*", text or "")
    return text
