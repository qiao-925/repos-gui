#!/bin/bash
# 日志输出函数

# 获取时间戳
_get_timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

# 带时间戳的日志函数（输出到 stderr，避免被命令替换捕获）
print_info() {
    echo -e "[$(_get_timestamp)] ${BLUE}ℹ${NC} $1" >&2
}

print_warning() {
    echo -e "[$(_get_timestamp)] ${YELLOW}⚠${NC} $1" >&2
}

print_error() {
    echo -e "[$(_get_timestamp)] ${RED}✗${NC} $1" >&2
}

print_success() {
    echo -e "[$(_get_timestamp)] ${GREEN}✓${NC} $1" >&2
}

print_debug() {
    # Debug 模式已关闭
    :
}

print_step() {
    echo -e "[$(_get_timestamp)] ${BLUE}→${NC} $1" >&2
}

# 详细操作日志（带时间戳和操作类型）
print_operation_start() {
    local operation=$1
    local details=$2
    echo -e "[$(_get_timestamp)] ${BLUE}[开始]${NC} $operation ${details:+($details)}" >&2
}

print_operation_end() {
    local operation=$1
    local status=$2  # success/fail/skip/warning
    local duration=$3  # 耗时（秒）
    local details=$4
    
    case "$status" in
        "success")
            echo -e "[$(_get_timestamp)] ${GREEN}[完成]${NC} $operation ${details:+($details)} ${duration:+[耗时: ${duration}秒]}" >&2
            ;;
        "fail"|"failure")
            echo -e "[$(_get_timestamp)] ${RED}[失败]${NC} $operation ${details:+($details)} ${duration:+[耗时: ${duration}秒]}" >&2
            ;;
        "skip")
            echo -e "[$(_get_timestamp)] ${YELLOW}[跳过]${NC} $operation ${details:+($details)} ${duration:+[耗时: ${duration}秒]}" >&2
            ;;
        "warning")
            echo -e "[$(_get_timestamp)] ${YELLOW}[警告]${NC} $operation ${details:+($details)} ${duration:+[耗时: ${duration}秒]}" >&2
            ;;
        *)
            echo -e "[$(_get_timestamp)] ${BLUE}[结束]${NC} $operation ${details:+($details)} ${duration:+[耗时: ${duration}秒]}" >&2
            ;;
    esac
}

# API 调用日志
print_api_call() {
    local api_name=$1
    local params=$2
    echo -e "[$(_get_timestamp)] ${BLUE}[API调用]${NC} $api_name ${params:+($params)}" >&2
}

# 命令执行日志
print_command() {
    local cmd=$1
    echo -e "[$(_get_timestamp)] ${BLUE}[执行命令]${NC} $cmd" >&2
}

