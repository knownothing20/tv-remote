# -*- coding: utf-8 -*-
"""马卡龙小电视图标：用 Pillow 绘制的双态图标（黑屏 / 亮屏）。

设计要点：机身两态完全一致，仅屏幕亮暗不同；机身靠上沿高光、下沿暗带、
内圈釉光、边框内凹形成质感。见 docs/ICONS.md。
"""
from __future__ import annotations

import os

from PIL import Image, ImageChops, ImageDraw, ImageFont

BASE = 1024
U = BASE / 160.0
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]

C_BODY = (169, 229, 203)
C_BODY_TOP = (196, 241, 221)
C_BODY_BOT = (143, 211, 178)
C_RIM = (232, 255, 245)
C_OUTLINE = (111, 194, 160)
C_BEZEL = (247, 255, 252)
C_BEZEL_TOP = (223, 242, 233)
C_ANT = (107, 191, 155)
C_PINK = (255, 183, 201)
C_YELLOW = (255, 221, 151)
C_FEET = (147, 216, 183)
C_FEET_HI = (186, 238, 215)
C_SCR_OFF = (35, 40, 48)
C_SCR_EDGE_OFF = (58, 66, 78)
C_SCR_ON = (241, 253, 255)
C_SCR_BAND = (166, 223, 255)


def _bx(box):
    return [v * U for v in box]


def _layer():
    return Image.new("RGBA", (BASE, BASE), (0, 0, 0, 0))


def _mask(box, r):
    m = Image.new("L", (BASE, BASE), 0)
    ImageDraw.Draw(m).rounded_rectangle(_bx(box), radius=r * U, fill=255)
    return m


def _band(img, box, r, color, alpha, clip):
    lay = _layer()
    ImageDraw.Draw(lay).rounded_rectangle(_bx(box), radius=r * U, fill=color + (alpha,))
    lay.putalpha(ImageChops.multiply(lay.getchannel("A"), clip))
    return Image.alpha_composite(img, lay)


def _poly(img, pts, alpha, clip):
    lay = _layer()
    ImageDraw.Draw(lay).polygon([(x * U, y * U) for x, y in pts], fill=(255, 255, 255, alpha))
    lay.putalpha(ImageChops.multiply(lay.getchannel("A"), clip))
    return Image.alpha_composite(img, lay)


def draw_tv(lit: bool) -> Image.Image:
    """绘制 1024×1024 的电视图标；lit=True 为已连接（亮屏）。"""
    img = Image.new("RGBA", (BASE, BASE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    for fx in (40, 102):
        d.rounded_rectangle(_bx((fx, 137, fx + 18, 148)), radius=5.5 * U, fill=C_FEET)
        d.rounded_rectangle(_bx((fx, 137, fx + 18, 140.5)), radius=1.75 * U, fill=C_FEET_HI + (255,))

    w = 4.5 * U
    for x0, y0, x1, y1 in ((62, 40, 40, 14), (98, 40, 120, 14)):
        d.line([(x0 * U, y0 * U), (x1 * U, y1 * U)], fill=C_ANT + (255,), width=int(round(w)))
        for px, py in ((x0, y0), (x1, y1)):
            d.ellipse([px * U - w / 2, py * U - w / 2, px * U + w / 2, py * U + w / 2], fill=C_ANT + (255,))

    d.ellipse(_bx((33.5, 7.5, 46.5, 20.5)), fill=C_PINK + (255,))
    d.ellipse(_bx((113.5, 7.5, 126.5, 20.5)), fill=C_YELLOW + (255,))
    d.ellipse(_bx((35.7, 9.7, 39.5, 13.5)), fill=(255, 255, 255, 217))
    d.ellipse(_bx((115.7, 9.7, 119.5, 13.5)), fill=(255, 255, 255, 204))
    d.ellipse(_bx((59.4, 39.4, 64.6, 44.6)), fill=(124, 201, 168, 255))
    d.ellipse(_bx((95.4, 39.4, 100.6, 44.6)), fill=(124, 201, 168, 255))

    body = (8, 40, 152, 142)
    d.rounded_rectangle(_bx(body), radius=20 * U, fill=C_BODY + (255,))
    body_mask = _mask(body, 20)
    img = _band(img, (8, 40, 152, 56), 8, C_BODY_TOP, 255, body_mask)
    img = _band(img, (8, 116, 152, 142), 12, C_BODY_BOT, 255, body_mask)

    rim = _layer()
    ImageDraw.Draw(rim).rounded_rectangle(
        _bx((10.5, 42.5, 149.5, 139.5)), radius=18 * U, outline=C_RIM + (217,), width=int(round(1.2 * U))
    )
    img = Image.alpha_composite(img, rim)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(_bx(body), radius=20 * U, outline=C_OUTLINE + (255,), width=int(round(2.5 * U)))

    bezel = (19, 51, 141, 131)
    d.rounded_rectangle(_bx(bezel), radius=12 * U, fill=C_BEZEL + (255,))
    bezel_mask = _mask(bezel, 12)
    img = _band(img, (19, 51, 141, 60), 6, C_BEZEL_TOP, 255, bezel_mask)
    img = _band(img, (19, 124, 141, 131), 4, (255, 255, 255), 255, bezel_mask)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(_bx(bezel), radius=12 * U, outline=(217, 238, 229, 255), width=int(round(1 * U)))

    scr = (25, 57, 135, 125)
    d.rounded_rectangle(_bx(scr), radius=8 * U, fill=(C_SCR_ON if lit else C_SCR_OFF) + (255,))
    scr_mask = _mask(scr, 8)
    if lit:
        img = _band(img, (25, 101, 135, 125), 8, C_SCR_BAND, 255, scr_mask)

    a1, a2 = (41, 26) if lit else (13, 9)
    img = _poly(img, [(25, 57), (62, 57), (34, 125), (25, 125)], a1, scr_mask)
    img = _poly(img, [(70, 57), (86, 57), (58, 125), (42, 125)], a2, scr_mask)

    d = ImageDraw.Draw(img)
    if lit:
        d.rounded_rectangle(_bx((33, 64, 87, 72)), radius=4 * U, fill=(255, 255, 255, 255))
        d.rounded_rectangle(_bx(scr), radius=8 * U, outline=(255, 255, 255, 153), width=int(round(1 * U)))
    else:
        d.rounded_rectangle(_bx(scr), radius=8 * U, outline=C_SCR_EDGE_OFF + (255,), width=int(round(1 * U)))
    return img


def tray_image(lit: bool, px: int = 64) -> Image.Image:
    return draw_tv(lit).resize((px, px), Image.LANCZOS)


def _font(size: int):
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc",
              r"C:\Windows\Fonts\simhei.ttf", "/System/Library/Fonts/PingFang.ttc",
              "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"):
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default(size)


def export_icons(dest: str) -> list[str]:
    """输出 tv_on.ico / tv_off.ico（多尺寸）与 256px PNG。"""
    os.makedirs(dest, exist_ok=True)
    made = []
    for name, lit in (("tv_off", False), ("tv_on", True)):
        im = draw_tv(lit)
        ico = os.path.join(dest, name + ".ico")
        im.resize((256, 256), Image.LANCZOS).save(ico, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
        png = os.path.join(dest, name + "_256.png")
        im.save(png)
        made += [ico, png]
    return made


def make_preview(path: str) -> str:
    """生成用于 README 的预览图（两态 + 多尺寸任务栏效果）。"""
    off, on = draw_tv(False), draw_tv(True)
    canvas = Image.new("RGB", (900, 560), (244, 245, 247))
    d = ImageDraw.Draw(canvas)
    d.text((40, 26), "TrayTVAdmin 图标集 · 未连接 / 已连接", fill=(30, 34, 40), font=_font(24))
    for i, (im, cap) in enumerate(((off, "未连接 · 屏幕熄灭"), (on, "已连接 · 屏幕点亮"))):
        big = im.resize((220, 220), Image.LANCZOS)
        x = 90 + i * 400
        canvas.paste(big, (x, 70), big)
        d.text((x + 20, 300), cap, fill=(60, 65, 72), font=_font(19))

    for y, bg, fg, label in ((350, (30, 33, 38), (138, 144, 153), "深色任务栏"),
                             (425, (242, 243, 245), (122, 127, 135), "浅色任务栏")):
        d.rounded_rectangle([40, y, 860, y + 60], radius=10, fill=bg)
        x = 70
        for size in (32, 24, 16):
            for src in (off, on):
                thumb = src.resize((size, size), Image.LANCZOS)
                canvas.paste(thumb, (x, y + (60 - size) // 2), thumb)
                x += size + 18
            x += 34
        d.text((700, y + 18), label, fill=fg, font=_font(17))

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    canvas.save(path)
    return path
