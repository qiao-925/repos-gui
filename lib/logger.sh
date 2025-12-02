#!/bin/bash
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

# 颜色定义
readonly COLOR_RESET='\033[0m'
readonly COLOR_INFO='\033[0;36m'      # 青色
readonly COLOR_SUCCESS='\033[0;32m'   # 绿色
readonly COLOR_ERROR='\033[0;31m'     # 红色
readonly COLOR_WARNING='\033[0;33m'   # 黄色

# 获取时间戳
_get_timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

# 输出信息日志
log_info() {
    local message="$1"
    echo -e "${COLOR_INFO}[INFO]${COLOR_RESET} [$(date '+%Y-%m-%d %H:%M:%S')] $message"
}

# 输出成功日志
log_success() {
    local message="$1"
    echo -e "${COLOR_SUCCESS}[SUCCESS]${COLOR_RESET} [$(date '+%Y-%m-%d %H:%M:%S')] $message"
}

# 输出错误日志
log_error() {
    local message="$1"
    echo -e "${COLOR_ERROR}[ERROR]${COLOR_RESET} [$(date '+%Y-%m-%d %H:%M:%S')] $message" >&2
}

# 输出警告日志
log_warning() {
    local message="$1"
    echo -e "${COLOR_WARNING}[WARNING]${COLOR_RESET} [$(date '+%Y-%m-%d %H:%M:%S')] $message"
}

