"""Watch handoff state and target files for completion.

Two modes:
  --block     Block until review_ready (for use inside Windsurf run_command)
  --daemon    Run as background watcher with desktop notifications

Detection strategy (layered):
  1. If state.json already shows review_ready → done immediately
  2. If Cursor wrote review_ready via callback → detect on next poll
  3. If target files changed and stayed stable for --quiet-sec → auto-detect
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
HANDOFF_DIR = ROOT_DIR / "handoff"
STATE_PATH = HANDOFF_DIR / "state.json"

IS_WINDOWS = sys.platform == "win32"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Watch handoff state for Cursor completion")
    parser.add_argument("--block", action="store_true", help="Block until review_ready (for Windsurf run_command)")
    parser.add_argument("--daemon", action="store_true", help="Run as background watcher with notifications")
    parser.add_argument("--interval", type=int, default=10, help="Poll interval in seconds (default: 10)")
    parser.add_argument("--quiet-sec", type=int, default=90, help="Seconds of no file change before auto-detect (default: 90)")
    parser.add_argument("--timeout", type=int, default=600, help="Max wait time in seconds (default: 600)")
    return parser.parse_args()


def read_state() -> dict | None:
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def get_fingerprints(paths: list[str]) -> dict[str, str | None]:
    result = {}
    for rel in paths:
        abs_path = ROOT_DIR / rel
        if abs_path.is_file():
            import hashlib
            result[rel] = hashlib.sha256(abs_path.read_bytes()).hexdigest()
        else:
            result[rel] = None
    return result


def run_detect() -> bool:
    """Run handoff_state.py detect. Returns True if review_ready."""
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT_DIR / "scripts" / "handoff_state.py"), "detect"],
            capture_output=True, text=True, cwd=str(ROOT_DIR), timeout=30,
        )
        return "review_ready" in result.stdout
    except Exception as exc:
        print(f"  detect error: {exc}", file=sys.stderr)
        return False


def notify(title: str, message: str) -> None:
    if IS_WINDOWS:
        try:
            from ctypes import windll
            # Windows balloon tip via PowerShell
            ps_cmd = (
                f'Add-Type -AssemblyName System.Windows.Forms; '
                f'$n = New-Object System.Windows.Forms.NotifyIcon; '
                f'$n.Icon = [System.Drawing.SystemIcons]::Information; '
                f'$n.Visible = $true; '
                f'$n.ShowBalloonTip(5000, \'{title}\', \'{message}\', \'Info\')'
            )
            subprocess.run(["powershell", "-Command", ps_cmd], timeout=10, capture_output=True)
        except Exception:
            print(f"[NOTIFY] {title}: {message}")
    else:
        print(f"[NOTIFY] {title}: {message}")


def watch(block: bool, daemon: bool, interval: int, quiet_sec: int, timeout: int) -> int:
    mode = "block" if block else "daemon" if daemon else "block"
    print(f"watch_handoff: mode={mode}, interval={interval}s, quiet={quiet_sec}s, timeout={timeout}s")

    start = time.time()
    last_change_time: float | None = None
    prev_fingerprints: dict[str, str | None] = {}

    while True:
        elapsed = time.time() - start
        if elapsed > timeout:
            print(f"watch_handoff: timeout after {timeout}s")
            return 2

        state = read_state()
        if state is None:
            print(f"  [{int(elapsed)}s] no state.json yet, waiting...")
            time.sleep(interval)
            continue

        status = state.get("status", "")

        # Already review_ready — done
        if status == "review_ready":
            print(f"watch_handoff: review_ready (changed_files: {len(state.get('changed_files', []))})")
            if daemon:
                notify("Handoff Ready", "Cursor may have finished. Review ready.")
            return 0

        # Not awaiting — nothing to watch
        if status != "awaiting_cursor":
            print(f"watch_handoff: status={status}, nothing to watch")
            return 0

        # Check target file changes
        target_files = state.get("target_files", [])
        current_fps = get_fingerprints(target_files)
        baseline_fps = state.get("baseline_fingerprints", {})

        changed_now = [
            rel for rel in target_files
            if current_fps.get(rel) != baseline_fps.get(rel)
        ]

        if changed_now:
            if current_fps != prev_fingerprints:
                last_change_time = time.time()
                prev_fingerprints = dict(current_fps)
                print(f"  [{int(elapsed)}s] files changing: {changed_now}")
            elif last_change_time is not None:
                quiet_elapsed = time.time() - last_change_time
                if quiet_elapsed >= quiet_sec:
                    print(f"  [{int(elapsed)}s] quiet for {quiet_sec}s, running detect...")
                    if run_detect():
                        state = read_state()
                        if state and state.get("status") == "review_ready":
                            print(f"watch_handoff: review_ready (auto-detected)")
                            if daemon:
                                notify("Handoff Ready", "Files stable, auto-detected as review_ready.")
                            return 0
        else:
            if not block and not daemon:
                # One-shot check: no changes yet
                print(f"  [{int(elapsed)}s] no target file changes yet")

        time.sleep(interval)


def main() -> int:
    args = parse_args()
    if not args.block and not args.daemon:
        args.block = True  # default to block mode
    return watch(block=args.block, daemon=args.daemon, interval=args.interval,
                 quiet_sec=args.quiet_sec, timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
