from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PROMPT_PATH = ROOT_DIR / "handoff" / "cursor-prompt.md"
DEFAULT_WINDOW_QUERY = "Cursor"
HANDOFF_STATE_SCRIPT = ROOT_DIR / "scripts" / "handoff_state.py"
IS_WINDOWS = sys.platform == "win32"


class RelayError(RuntimeError):
    pass


# ── Virtual key codes (Windows) ──────────────────────────────────────

_VK_CONTROL = 0x11
_VK_V = 0x56
_VK_RETURN = 0x0D
_VK_TAB = 0x09
_VK_L = 0x4C
_KEYEVENTF_KEYUP = 0x0002

_SEND_KEY_MAP: dict[str, int] = {
    "return": _VK_RETURN,
    "enter": _VK_RETURN,
    "tab": _VK_TAB,
}


def _resolve_send_key_vk(name: str) -> int:
    key = name.casefold()
    if key in _SEND_KEY_MAP:
        return _SEND_KEY_MAP[key]
    if len(key) == 1:
        return ord(key.upper())
    raise RelayError(f"Unknown send-key name on Windows: {name}")


# ── Shared helpers ───────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--action",
        choices=("check", "paste", "paste-and-send"),
        default="check",
    )
    parser.add_argument("--file", default=str(DEFAULT_PROMPT_PATH))
    parser.add_argument("--window-query", default=DEFAULT_WINDOW_QUERY)
    parser.add_argument("--activate-delay", type=float, default=0.4)
    parser.add_argument("--send-delay", type=float, default=0.2)
    parser.add_argument("--send-key")
    parser.add_argument("--chat-focus", action="store_true",
                        help="Enable Ctrl+L chat focus (default: disabled for safety)")
    return parser.parse_args()


def run_command(command: list[str], capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=capture_output,
        )
    except FileNotFoundError as exc:
        raise RelayError(f"Missing command: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        detail = f" ({stderr})" if stderr else ""
        raise RelayError(f"Command failed: {' '.join(command)}{detail}") from exc


def read_prompt_file(path: Path) -> str:
    if not path.exists():
        raise RelayError(f"Prompt file not found: {path}")

    content = path.read_text(encoding="utf-8")
    if not content.strip():
        raise RelayError(f"Prompt file is empty: {path}")
    return content


def format_check_output(prompt_path: Path, window_id: str, window_title: str, content: str, clipboard_command: str) -> str:
    lines = [
        "relay check ok",
        f"prompt_file: {prompt_path}",
        f"prompt_chars: {len(content)}",
        f"window_id: {window_id}",
        f"window_title: {window_title}",
        f"clipboard: {clipboard_command}",
        f"platform: {'windows' if IS_WINDOWS else 'linux'}",
    ]
    return "\n".join(lines)


def mark_handoff_awaiting(action: str) -> str:
    command = [
        sys.executable,
        str(HANDOFF_STATE_SCRIPT),
        "mark-awaiting",
        "--relay-action",
        action,
    ]

    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        stdout = exc.stdout.strip() if exc.stdout else ""
        detail = stderr or stdout or "unknown error"
        return f"handoff_state_warning: {detail}"

    return result.stdout.strip()


# ── Windows implementation ────────────────────────────────────────────

def _win_key_down(vk: int) -> None:
    import ctypes
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)


def _win_key_up(vk: int) -> None:
    import ctypes
    ctypes.windll.user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)


def _win_ensure_dependencies() -> str:
    return "powershell"


def _win_find_window(window_query: str) -> tuple[int, int, str]:
    """Find window by title query. Returns (pid, hwnd, title)."""
    query = window_query.casefold()
    ps_command = (
        "Get-Process | Where-Object { $_.MainWindowTitle -ne '' }"
        " | Select-Object Id, MainWindowHandle, MainWindowTitle | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RelayError(f"Failed to enumerate windows via PowerShell") from exc

    raw = result.stdout.strip()
    if not raw:
        raise RelayError(f"No window matched query: {window_query}")

    entries = json.loads(raw)
    if isinstance(entries, dict):
        entries = [entries]

    for entry in entries:
        title = entry.get("MainWindowTitle", "")
        if query in title.casefold():
            pid = entry["Id"]
            # MainWindowHandle is an IntPtr, convert to int
            hwnd_raw = entry.get("MainWindowHandle", 0)
            hwnd = int(hwnd_raw) if hwnd_raw else 0
            return pid, hwnd, title

    raise RelayError(f"No window matched query: {window_query}")


def _win_copy_to_clipboard(content: str) -> None:
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"],
            input=content, text=True, check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RelayError("Failed to copy content via PowerShell Set-Clipboard") from exc


def _win_get_foreground_title() -> str:
    """Return the title of the current foreground window."""
    ps_command = (
        "Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices;"
        " public class Win { [DllImport(\"user32.dll\")] public static extern IntPtr GetForegroundWindow();"
        " [DllImport(\"user32.dll\", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder lpString, int nMaxCount); }';"
        "$h = [Win]::GetForegroundWindow(); $sb = New-Object System.Text.StringBuilder 512;"
        "[Win]::GetWindowText($h, $sb, 512) | Out-Null; $sb.ToString()"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _win_force_foreground(hwnd: int) -> None:
    """Force a window to foreground by hwnd, bypassing Windows foreground lock.

    Strategy:
    1. Send Escape to dismiss any overlay (Windows Search, Start Menu, etc.)
    2. Use HWND_TOPMOST trick to force window to foreground
    3. Remove topmost flag and explicitly set foreground
    """
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32

    if not hwnd:
        raise RelayError("Cannot force foreground: hwnd is 0")

    # Step 0: Dismiss any overlay (Windows Search, Start Menu, etc.)
    # First try Escape keys, then force-close any non-main window that stole foreground
    VK_ESCAPE = 0x1B
    for _ in range(3):
        user32.keybd_event(VK_ESCAPE, 0, 0, 0)
        user32.keybd_event(VK_ESCAPE, 0, _KEYEVENTF_KEYUP, 0)
    time.sleep(0.1)

    # Check if foreground is still an overlay (not our target)
    fg = user32.GetForegroundWindow()
    if fg != hwnd:
        # Try to close the foreground window if it's not the target
        # This handles Windows Search, Start Menu, etc.
        WM_CLOSE = 0x0010
        user32.PostMessageW(fg, WM_CLOSE, 0, 0)
        time.sleep(0.3)

    # Ensure correct types for Win32 API
    user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL

    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_SHOWWINDOW = 0x0040
    HWND_TOPMOST = wintypes.HWND(-1)
    HWND_NOTOPMOST = wintypes.HWND(-2)

    # Step 1: Set as topmost (this forces it to foreground)
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    time.sleep(0.1)

    # Step 2: Remove topmost flag (keep it in foreground but not always-on-top)
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    time.sleep(0.1)

    # Step 3: Explicitly set foreground + restore if minimized
    SW_RESTORE = 9
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    time.sleep(0.2)


def _win_activate_window(hwnd: int, delay: float, expected_query: str = "") -> None:
    try:
        _win_force_foreground(hwnd)
    except (subprocess.CalledProcessError, OSError) as exc:
        raise RelayError(f"Failed to activate window hwnd={hwnd}") from exc
    if delay > 0:
        time.sleep(delay)

    # Verify foreground window matches expected query before sending keys
    if expected_query:
        fg_title = _win_get_foreground_title()
        if expected_query.casefold() not in fg_title.casefold():
            raise RelayError(
                f"Foreground verification failed: expected '{expected_query}' in "
                f"'{fg_title}', but foreground is '{fg_title}'. "
                f"Aborting paste to prevent sending content to wrong window."
            )


def _win_open_cursor_chat() -> None:
    """Open Cursor's chat panel with Ctrl+L, then wait for it to focus."""
    _win_key_down(_VK_CONTROL)
    _win_key_down(_VK_L)
    _win_key_up(_VK_L)
    _win_key_up(_VK_CONTROL)
    time.sleep(0.3)  # Wait for chat panel to open and input to focus


def _win_paste_clipboard() -> None:
    _win_key_down(_VK_CONTROL)
    _win_key_down(_VK_V)
    _win_key_up(_VK_V)
    _win_key_up(_VK_CONTROL)


def _win_send_key(send_key: str, delay: float) -> None:
    if delay > 0:
        time.sleep(delay)
    vk = _resolve_send_key_vk(send_key)
    _win_key_down(vk)
    _win_key_up(vk)


# ── Linux implementation (original) ─────────────────────────────────

def _linux_ensure_dependencies() -> str:
    missing = [name for name in ("wmctrl", "xdotool") if shutil.which(name) is None]
    if missing:
        raise RelayError(f"Missing required commands: {', '.join(missing)}")

    for candidate in ("xclip", "wl-copy", "xsel"):
        if shutil.which(candidate):
            return candidate

    raise RelayError("Missing clipboard command: xclip, wl-copy, or xsel")


def _linux_find_window(window_query: str) -> tuple[str, str]:
    result = run_command(["wmctrl", "-lx"], capture_output=True)
    matches: list[tuple[str, str]] = []
    query = window_query.casefold()

    for line in result.stdout.splitlines():
        if query not in line.casefold():
            continue
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        matches.append((parts[0], parts[4]))

    if not matches:
        raise RelayError(f"No window matched query: {window_query}")

    return matches[0]


def _linux_copy_to_clipboard(content: str, clipboard_command: str) -> None:
    if clipboard_command == "xclip":
        command = ["xclip", "-selection", "clipboard"]
    elif clipboard_command == "wl-copy":
        command = ["wl-copy"]
    else:
        command = ["xsel", "--clipboard", "--input"]

    try:
        subprocess.run(command, input=content, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise RelayError(f"Failed to copy content with {clipboard_command}") from exc


def _linux_activate_window(window_id: str, delay: float) -> None:
    run_command(["xdotool", "windowactivate", "--sync", window_id])
    if delay > 0:
        time.sleep(delay)


def _linux_paste_clipboard() -> None:
    run_command(["xdotool", "key", "--clearmodifiers", "ctrl+v"])


def _linux_send_key(send_key: str, delay: float) -> None:
    if delay > 0:
        time.sleep(delay)
    run_command(["xdotool", "key", "--clearmodifiers", send_key])


# ── Main ─────────────────────────────────────────────────────────────

def main() -> int:
    args = parse_args()
    prompt_path = Path(args.file).expanduser().resolve()

    try:
        content = read_prompt_file(prompt_path)

        if IS_WINDOWS:
            clipboard_command = _win_ensure_dependencies()
            window_pid, window_hwnd, window_title = _win_find_window(args.window_query)

            if args.action == "check":
                print(format_check_output(prompt_path, str(window_pid), window_title, content, clipboard_command))
                return 0

            _win_activate_window(window_hwnd, args.activate_delay, expected_query=args.window_query)
            if args.chat_focus:
                _win_open_cursor_chat()
            _win_copy_to_clipboard(content)
            time.sleep(0.1)
            _win_paste_clipboard()

            if args.action == "paste-and-send":
                if not args.send_key:
                    raise RelayError("--send-key is required for paste-and-send")
                _win_send_key(args.send_key, args.send_delay)
        else:
            clipboard_command = _linux_ensure_dependencies()
            window_id, window_title = _linux_find_window(args.window_query)

            if args.action == "check":
                print(format_check_output(prompt_path, window_id, window_title, content, clipboard_command))
                return 0

            _linux_copy_to_clipboard(content, clipboard_command)
            _linux_activate_window(window_id, args.activate_delay)
            _linux_paste_clipboard()

            if args.action == "paste-and-send":
                if not args.send_key:
                    raise RelayError("--send-key is required for paste-and-send")
                _linux_send_key(args.send_key, args.send_delay)

        handoff_state_output = mark_handoff_awaiting(args.action)

        print(f"relay action complete: {args.action}")
        print(f"target_window: {window_title}")
        print(f"prompt_file: {prompt_path}")
        if handoff_state_output:
            print(handoff_state_output)
        return 0
    except RelayError as exc:
        print(f"relay error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
