#!/bin/bash
# 日志输出模块：提供统一的日志输出功能
#
# 主要功能：
#   - print_info()：输出信息日志
#   - print_warning()：输出警告日志
#   - print_error()：输出错误日志
#   - print_success()：输出成功日志
#   - print_step()：输出步骤日志
#   - log_api_call()：记录 API 调用（带计时）
#
# 特性：
#   - 所有日志输出到 stderr，避免被命令替换捕获
#   - 自动添加时间戳
#   - API 调用自动计时

# ANSI 颜色代码（全局常量，供其他模块使用）
COLOR_RESET='\033[0m'
COLOR_GREEN='\033[0;32m'
COLOR_RED='\033[0;31m'

# 获取时间戳
_get_timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

# 带时间戳的日志函数（输出到 stderr，避免被命令替换捕获）
print_info() {
    echo "[$(_get_timestamp)] ℹ️  $1" >&2
}

print_warning() {
    echo "[$(_get_timestamp)] ⚠️  $1" >&2
}

print_error() {
    echo "[$(_get_timestamp)] ❌ $1" >&2
}

print_success() {
    echo "[$(_get_timestamp)] ✅ $1" >&2
}


print_step() {
    echo "[$(_get_timestamp)] ➜  $1" >&2
}

# 计算时间差（兼容 Windows，不依赖 bc）
_calculate_duration() {
    local start=$1
    local end=$2
    
    # 提取整数部分和小数部分
    local start_int=${start%.*}
    local start_frac=${start#*.}
    local end_int=${end%.*}
    local end_frac=${end#*.}
    
    # 如果没有小数部分，使用整数秒
    if [ -z "$start_frac" ] || [ "$start_frac" = "$start" ]; then
        local duration=$((end_int - start_int))
        echo "$duration"
        return 0
    fi
    
    # 有小数部分，尝试精确计算
    if command -v bc >/dev/null 2>&1; then
        local duration=$(echo "scale=2; $end - $start" | bc 2>/dev/null)
        if [ -n "$duration" ]; then
            echo "$duration"
            return 0
        fi
    fi
    
    # 回退到整数秒计算
    local duration=$((end_int - start_int))
    echo "$duration"
}

# 常量定义
readonly ERROR_MSG_MAX_LENGTH=200  # 错误信息最大显示长度

# API 调用日志函数（带计时）
# 参数: operation_description command [args...]
# 用法: log_api_call "获取仓库列表" gh repo list --limit 1000
log_api_call() {
    local description="$1"
    shift
    
    print_info "🌐 [API调用] 开始: $description"
    
    # 获取开始时间（尝试高精度，回退到秒）
    local start_time
    if date +%s.%N &>/dev/null; then
        start_time=$(date +%s.%N)
    else
        start_time=$(date +%s)
    fi
    
    # 执行命令并捕获输出和退出码
    local output
    local exit_code
    output=$("$@" 2>&1)
    exit_code=$?
    
    # 获取结束时间
    local end_time
    if date +%s.%N &>/dev/null; then
        end_time=$(date +%s.%N)
    else
        end_time=$(date +%s)
    fi
    
    local duration=$(_calculate_duration "$start_time" "$end_time")
    
    if [ "$exit_code" -eq 0 ]; then
        print_success "✅ [API调用] 完成: $description (耗时: ${duration}秒)"
    else
        print_error "❌ [API调用] 失败: $description (耗时: ${duration}秒, 退出码: $exit_code)"
        if [ -n "$output" ]; then
            # 限制错误信息长度，避免输出过长
            local error_msg="${output:0:$ERROR_MSG_MAX_LENGTH}"
            if [ ${#output} -gt $ERROR_MSG_MAX_LENGTH ]; then
                error_msg="${error_msg}..."
            fi
            print_error "   错误信息: $error_msg"
        fi
    fi
    
    # 返回命令的输出（用于进一步处理）
    echo "$output"
    return $exit_code
}

