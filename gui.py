#!/usr/bin/env python3
# GUI entrypoint (thin wrapper)

import os
import sys
from pathlib import Path

# Enable AT-SPI accessibility bridge
os.environ["QT_ACCESSIBILITY"] = "1"
os.environ["QT_LINUX_ACCESSIBILITY_ALWAYS_ON"] = "1"

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from src.gh_repos_sync.ui.main_window import main

if __name__ == '__main__':
    main()
