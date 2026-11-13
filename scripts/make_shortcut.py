#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 Windows 快捷方式（.lnk），不依赖 COM / pywin32。

按 [MS-SHLLINK] 规范写出最小可用的 Shell Link：
Header + LinkInfo（含 VolumeID / LocalBasePath / CommonPathSuffix）+ StringData。
"""
from __future__ import annotations

import os
import struct
import sys

CLSID = bytes([
    0x01, 0x14, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00,
    0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46,
])

HAS_LINK_INFO = 0x00000002
HAS_NAME = 0x00000004
HAS_WORKING_DIR = 0x00000010
HAS_ICON_LOCATION = 0x00000040
IS_UNICODE = 0x00000080


def _ansi(text: str) -> bytes:
    return text.encode("mbcs", "replace") + b"\x00"


def _ustr(text: str) -> bytes:
    raw = text.encode("utf-16-le") + b"\x00\x00"
    return struct.pack("<H", len(raw) // 2) + raw


def build(target: str, working_dir: str, icon: str, name: str) -> bytes:
    target = os.path.abspath(target)
    working_dir = os.path.abspath(working_dir)
    icon = os.path.abspath(icon)

    flags = HAS_LINK_INFO | HAS_NAME | HAS_WORKING_DIR | HAS_ICON_LOCATION | IS_UNICODE

    header = struct.pack("<I", 0x4C) + CLSID
    header += struct.pack("<I", flags)
    header += struct.pack("<I", 0x00000020)      # FILE_ATTRIBUTE_ARCHIVE
    header += struct.pack("<Q", 0)               # CreationTime
    header += struct.pack("<Q", 0)               # AccessTime
    header += struct.pack("<Q", 0)               # WriteTime
    header += struct.pack("<I", 0)               # FileSize
    header += struct.pack("<i", 0)               # IconIndex
    header += struct.pack("<I", 1)               # ShowCommand = SW_SHOWNORMAL
    header += struct.pack("<H", 0)               # HotKey
    header += struct.pack("<H", 0)               # Reserved1
    header += struct.pack("<I", 0)               # Reserved2
    header += struct.pack("<I", 0)               # Reserved3
    assert len(header) == 0x4C, len(header)

    base_path = _ansi(target)
    suffix = b"\x00"
    label = b"\x00"                              # 空卷标
    vol_size = 16 + len(label)
    vol_id = struct.pack("<IIII", vol_size, 3, 0, 0x10) + label

    link_info_header_size = 0x1C
    vol_off = link_info_header_size
    base_off = vol_off + vol_size
    suffix_off = base_off + len(base_path)
    link_info_size = suffix_off + len(suffix)

    link_info = struct.pack("<IIIIIII",
                            link_info_size, link_info_header_size, 1,
                            vol_off, base_off, 0, suffix_off)
    link_info += vol_id + base_path + suffix

    strings = _ustr(name) + _ustr(working_dir) + _ustr(icon)
    return header + link_info + strings


def write_lnk(path: str, target: str, working_dir: str, icon: str, name: str) -> str:
    data = build(target, working_dir, icon, name)
    with open(path, "wb") as f:
        f.write(data)
    return path


def describe(path: str) -> dict:
    """粗解析，用于自检（不做完整规范解析）。"""
    with open(path, "rb") as f:
        data = f.read()
    info = {
        "size": len(data),
        "header_size": struct.unpack("<I", data[:4])[0],
        "flags": struct.unpack("<I", data[20:24])[0],
    }
    li_size = struct.unpack("<I", data[0x4C:0x50])[0]
    base_off = struct.unpack("<I", data[0x4C + 16:0x4C + 20])[0]
    start = 0x4C + base_off
    end = start
    while data[end] != 0:
        end += 1
    info["target"] = data[start:end].decode("mbcs", "replace")
    rest = data[0x4C + li_size:]
    parts, idx = [], 0
    while idx < len(rest) - 1:
        count = struct.unpack("<H", rest[idx:idx + 2])[0]
        if count == 0:
            break
        chunk = rest[idx + 2: idx + 2 + count * 2]
        parts.append(chunk.decode("utf-16-le").rstrip("\x00"))
        idx += 2 + count * 2
    info["strings"] = parts
    return info


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exe = os.path.join(root, "TrayTVAdmin.exe")
    lnk = os.path.join(root, "TrayTVAdmin.lnk")
    write_lnk(lnk, exe, root, exe, "电视管理后台")
    import json
    print(json.dumps(describe(lnk), ensure_ascii=False, indent=2))
