#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""入口：`python main.py`（托盘） / `python main.py --headless`（仅服务，Docker 用）"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

if "--headless" in sys.argv[1:]:
    from tvremote.headless import main  # noqa: E402
else:
    from tvremote.tray import main  # noqa: E402

if __name__ == "__main__":
    main()

