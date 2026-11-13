#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重新生成图标：assets/icons/*.ico 与 assets/preview/icons_preview.png"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from tvremote import icons  # noqa: E402


def main():
    made = icons.export_icons(os.path.join(ROOT, "assets", "icons"))
    made.append(icons.make_preview(os.path.join(ROOT, "assets", "preview", "icons_preview.png")))
    print("\n".join(made))


if __name__ == "__main__":
    main()
