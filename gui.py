#!/usr/bin/env python3
# GUI entrypoint (thin wrapper)

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gh_repos_sync.ui.main_window import main

if __name__ == '__main__':
    main()
