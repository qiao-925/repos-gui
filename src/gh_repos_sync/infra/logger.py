# 日志输出模块：提供统一的日志输出功能
#
# 主要功能：
#   - log_info()：输出信息日志
#   - log_success()：输出成功日志
#   - log_error()：输出错误日志
#   - log_warning()：输出警告日志
#
# 特性：
#   - 带时间戳
#   - 支持颜色输出（如果终端支持）

import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Tuple

from .paths import SCRIPT_DIR

# 尝试导入 colorama（Windows 颜色支持）
try:
    import colorama
    colorama.init()
    USE_COLORAMA = True
except ImportError:
    USE_COLORAMA = False

# ANSI 颜色代码
COLOR_RESET = '\033[0m'
COLOR_INFO = '\033[0;36m'      # 青色
COLOR_SUCCESS = '\033[0;32m'   # 绿色
COLOR_ERROR = '\033[0;31m'     # 红色
COLOR_WARNING = '\033[0;33m'   # 黄色

# GUI 日志回调（可选）
LOG_CALLBACK: Optional[Callable[[str, str, str], None]] = None
LOG_TO_STDOUT = True
LOG_TO_STDERR = True
LOG_DIR = SCRIPT_DIR / "logs"
LOG_FILE = LOG_DIR / "CloneX.log"


def get_log_state() -> Tuple[Optional[Callable[[str, str, str], None]], bool, bool]:
    """获取当前日志输出状态"""
    return LOG_CALLBACK, LOG_TO_STDOUT, LOG_TO_STDERR


def get_log_file_path() -> Path:
    """获取详细日志文件路径"""
    return LOG_FILE


def set_log_callback(
    callback: Optional[Callable[[str, str, str], None]],
    log_to_stdout: Optional[bool] = None,
    log_to_stderr: Optional[bool] = None
) -> None:
    """设置日志回调与输出开关（GUI 使用）"""
    global LOG_CALLBACK, LOG_TO_STDOUT, LOG_TO_STDERR
    LOG_CALLBACK = callback
    if log_to_stdout is not None:
        LOG_TO_STDOUT = log_to_stdout
    if log_to_stderr is not None:
        LOG_TO_STDERR = log_to_stderr


def _emit_callback(level: str, message: str, timestamp: str) -> None:
    """向 GUI 回调输出日志（不含颜色）"""
    if LOG_CALLBACK is None:
        return
    try:
        LOG_CALLBACK(level, message, timestamp)
    except Exception:
        pass


def _get_timestamp() -> str:
    """获取时间戳"""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _format_plain_message(level: str, timestamp: str, message: str) -> str:
    """格式化纯文本日志消息"""
    return f"[{level}] [{timestamp}] {message}"


def _format_message(level: str, color: str, message: str, timestamp: str) -> str:
    """格式化日志消息"""
    if USE_COLORAMA or sys.stdout.isatty():
        return f"{color}[{level}]{COLOR_RESET} [{timestamp}] {message}"
    else:
        return _format_plain_message(level, timestamp, message)


def _append_file_log(level: str, message: str, timestamp: str) -> None:
    """追加写入详细日志文件"""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(_format_plain_message(level, timestamp, message))
            handle.write("\n")
    except Exception:
        pass


def log_info(message: str) -> None:
    """输出信息日志"""
    timestamp = _get_timestamp()
    _emit_callback("INFO", message, timestamp)
    _append_file_log("INFO", message, timestamp)
    if LOG_TO_STDOUT:
        print(_format_message("INFO", COLOR_INFO, message, timestamp))


def log_success(message: str) -> None:
    """输出成功日志"""
    timestamp = _get_timestamp()
    _emit_callback("SUCCESS", message, timestamp)
    _append_file_log("SUCCESS", message, timestamp)
    if LOG_TO_STDOUT:
        print(_format_message("SUCCESS", COLOR_SUCCESS, message, timestamp))


def log_error(message: str) -> None:
    """输出错误日志（输出到 stderr）"""
    timestamp = _get_timestamp()
    _emit_callback("ERROR", message, timestamp)
    _append_file_log("ERROR", message, timestamp)
    if LOG_TO_STDERR:
        formatted = _format_message("ERROR", COLOR_ERROR, message, timestamp)
        print(formatted, file=sys.stderr)


def log_warning(message: str) -> None:
    """输出警告日志"""
    timestamp = _get_timestamp()
    _emit_callback("WARNING", message, timestamp)
    _append_file_log("WARNING", message, timestamp)
    if LOG_TO_STDOUT:
        print(_format_message("WARNING", COLOR_WARNING, message, timestamp))


def log_debug(message: str) -> None:
    """输出调试日志（仅写入文件）"""
    _append_file_log("DEBUG", message, _get_timestamp())


def log_exception(message: str, exc: Exception) -> None:
    """输出异常日志，并将 traceback 写入详细日志文件"""
    log_error(f"{message} - {exc}")
    log_debug(traceback.format_exc().rstrip())
