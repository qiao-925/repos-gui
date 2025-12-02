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
from datetime import datetime

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


def _get_timestamp() -> str:
    """获取时间戳"""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _format_message(level: str, color: str, message: str) -> str:
    """格式化日志消息"""
    timestamp = _get_timestamp()
    if USE_COLORAMA or sys.stdout.isatty():
        return f"{color}[{level}]{COLOR_RESET} [{timestamp}] {message}"
    else:
        return f"[{level}] [{timestamp}] {message}"


def log_info(message: str) -> None:
    """输出信息日志"""
    print(_format_message("INFO", COLOR_INFO, message))


def log_success(message: str) -> None:
    """输出成功日志"""
    print(_format_message("SUCCESS", COLOR_SUCCESS, message))


def log_error(message: str) -> None:
    """输出错误日志（输出到 stderr）"""
    formatted = _format_message("ERROR", COLOR_ERROR, message)
    print(formatted, file=sys.stderr)


def log_warning(message: str) -> None:
    """输出警告日志"""
    print(_format_message("WARNING", COLOR_WARNING, message))

