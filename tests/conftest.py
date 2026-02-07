from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def _clear_shutdown_flag():
    from gh_repos_sync.core.process_control import clear_shutdown_request

    clear_shutdown_request()
    yield
    clear_shutdown_request()

