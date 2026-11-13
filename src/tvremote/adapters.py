# -*- coding: utf-8 -*-
"""机型适配器：把包名 / 进程名映射成中文名、角色与"能不能禁用"。

- 一个适配器 = ``adapters/<id>.json`` 一个文件，便于按机型独立维护与公开贡献
- 匹配依据：设备属性（``ro.product.model`` / ``ro.product.brand`` 等）
- 未匹配时返回空表，面板仍显示原始包名（不影响功能）

新增机型请看 ``docs/ADAPTERS.md``。
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

ADAPTER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "adapters")

POLICY_LABELS = {
    "avoid": "禁止改动",
    "keep": "保留",
    "optional": "可停用",
    "bloat": "建议停用",
}


@lru_cache(maxsize=1)
def _load_all() -> tuple:
    items = []
    try:
        names = sorted(os.listdir(ADAPTER_DIR))
    except OSError:
        return tuple()
    for name in names:
        if not name.endswith(".json") or name.startswith("_"):
            continue
        try:
            with open(os.path.join(ADAPTER_DIR, name), encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if data.get("id") and isinstance(data.get("packages"), dict):
            items.append(data)
    return tuple(items)


def list_adapters() -> list:
    return [
        {
            "id": a["id"],
            "name": a.get("name", ""),
            "vendor": a.get("vendor", ""),
            "reference_device": a.get("reference_device", ""),
            "packages": len(a.get("packages") or {}),
        }
        for a in _load_all()
    ]


def _matches(adapter: dict, props: dict) -> bool:
    rules = adapter.get("match") or {}
    if not rules:
        return False
    hit = 0
    for key, expected in rules.items():
        actual = str((props or {}).get(key, "") or "").strip()
        if not actual:
            continue
        wanted = expected if isinstance(expected, list) else [expected]
        if actual not in [str(w) for w in wanted]:
            return False
        hit += 1
    return hit > 0


def resolve(props: dict) -> dict | None:
    for adapter in _load_all():
        if _matches(adapter, props or {}):
            return adapter
    return None


def payload(props: dict) -> dict:
    """给面板用：命中的适配器 + 全部可用适配器列表。"""
    adapter = resolve(props)
    available = list_adapters()
    if not adapter:
        return {
            "matched": "",
            "name": "",
            "device": str((props or {}).get("ro.product.model", "") or ""),
            "packages": {},
            "available": available,
        }
    return {
        "matched": adapter["id"],
        "name": adapter.get("name", ""),
        "device": str((props or {}).get("ro.product.model", "") or ""),
        "reference_device": adapter.get("reference_device", ""),
        "packages": adapter.get("packages", {}),
        "available": available,
    }
