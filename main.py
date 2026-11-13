#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PyInstaller 入口 & 源码运行入口：python main.py [--selftest]"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from tvremote.tray import main  # noqa: E402

if __name__ == "__main__":
    main()
