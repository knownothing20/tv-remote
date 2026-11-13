#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AirPlay 广播探测（诊断工具，不属于运行时依赖）。

为什么需要它：Windows 上常有多进程占用 UDP 5353，普通的 mDNS 监听会抢不到响应。
这里改用 **QU（unicast-response）** 查询，直接单播到电视 IP，回复也走单播，
不依赖 5353 的 multicast 投递，因此在多进程环境下更可靠。

用法：
    python scripts/probe_airplay.py                # 自动探测本网段内的接收端
    python scripts/probe_airplay.py 192.168.1.10   # 指定电视 IP
"""
from __future__ import annotations

import re
import socket
import struct
import sys
import time

MDNS = "224.0.0.251"
PORT = 5353
SERVICES = ["_airplay._tcp.local", "_raop._tcp.local"]


def build_query(name: str) -> bytes:
    header = struct.pack("!HHHHHH", 0, 0, 1, 0, 0, 0)
    q = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".") if p)
    q += b"\x00" + struct.pack("!HH", 12, 1)   # QTYPE=PTR, 标准组播查询
    return header + q


def local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("223.5.5.5", 53))
        return s.getsockname()[0]
    except OSError:
        return "0.0.0.0"
    finally:
        s.close()


def decode_name(data: bytes, off: int) -> tuple[str, int]:
    parts, guard = [], 0
    while off < len(data) and guard < 64:
        guard += 1
        ln = data[off]
        if ln == 0:
            return ".".join(parts), off + 1
        if ln & 0xC0 == 0xC0:
            ptr = ((ln & 0x3F) << 8) | data[off + 1]
            sub, _ = decode_name(data, ptr)
            if sub:
                parts.append(sub)
            return ".".join(parts), off + 2
        parts.append(data[off + 1: off + 1 + ln].decode("utf-8", "ignore"))
        off += 1 + ln
    return ".".join(parts), off


def parse(data: bytes) -> list[dict]:
    try:
        _id, _flags, qd, an, ns, ar = struct.unpack("!HHHHHH", data[:12])
    except struct.error:
        return []
    off = 12
    for _ in range(qd):
        _, off = decode_name(data, off)
        off += 4
    out = []
    # 关键：TXT / SRV 常在 additional 段，必须一起遍历（an + ns + ar）
    for _ in range(an + ns + ar):
        name, off = decode_name(data, off)
        if off + 10 > len(data):
            break
        rtype, _cls, _ttl, rdlen = struct.unpack("!HHIH", data[off:off + 10])
        off += 10
        rdata = data[off:off + rdlen]
        off += rdlen
        item = {"name": name, "type": rtype}
        if rtype == 33 and len(rdata) >= 6:          # SRV
            item["port"] = struct.unpack("!H", rdata[4:6])[0]
        elif rtype == 16:                            # TXT
            txts = []
            i = 0
            while i < len(rdata):
                ln = rdata[i]
                txts.append(rdata[i + 1:i + 1 + ln].decode("utf-8", "ignore"))
                i += 1 + ln
            item["txt"] = txts
        out.append(item)
    return out


def probe(target: str | None, wait: float = 5.0) -> dict:
    """mDNS 响应默认发到 5353，因此必须绑 5353 并加入组播组才能收到。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("", PORT))
    except OSError as e:
        return {"error": f"绑定 5353 失败（可能被占用）: {e}"}
    try:
        sock.setsockopt(
            socket.IPPROTO_IP,
            socket.IP_ADD_MEMBERSHIP,
            socket.inet_aton(MDNS) + socket.inet_aton(local_ip()),
        )
    except OSError:
        pass
    sock.settimeout(0.4)

    for _ in range(2):                      # 发两轮，丢包也能命中
        for svc in SERVICES:
            try:
                sock.sendto(build_query(svc), (MDNS, PORT))
                if target:
                    sock.sendto(build_query(svc), (target, PORT))
            except OSError as e:
                return {"error": str(e)}
            time.sleep(0.15)

    found: dict[str, dict] = {}
    deadline = time.time() + wait
    while time.time() < deadline:
        try:
            data, addr = sock.recvfrom(9000)
        except socket.timeout:
            continue
        except OSError:
            break
        for rec in parse(data):
            key = rec["name"]
            entry = found.setdefault(key, {"name": key, "src": addr[0], "port": None, "txt": []})
            if rec.get("port"):
                entry["port"] = rec["port"]
            if rec.get("txt"):
                entry["txt"] = rec["txt"]
    sock.close()
    return found


def summarize(found: dict) -> list[str]:
    lines = []
    for name, e in found.items():
        txt = " ".join(e.get("txt") or [])
        dev = re.search(r"deviceid=([0-9A-Fa-f:]+)", txt)
        model = re.search(r"model=([^ \"]+)", txt)
        if not (dev or e.get("port")):
            continue
        lines.append(
            f"{name}\n    来源: {e['src']}  端口: {e.get('port') or '-'}  "
            f"model: {model.group(1) if model else '-'}  "
            f"deviceid: {dev.group(1) if dev else '-'}"
        )
    return lines


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    res = probe(target)
    if isinstance(res, dict) and res.get("error"):
        print("探测失败:", res["error"])
        raise SystemExit(1)
    lines = summarize(res)
    print("\n".join(lines) if lines else "未收到任何 AirPlay 响应")
    print(f"\n共 {len(lines)} 个服务条目（目标: {target or '组播'}）")
