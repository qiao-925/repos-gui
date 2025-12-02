#!/bin/bash
# 工具函数模块：提供字符串和数组转换的通用工具函数
#
# 主要功能：
#   - string_to_array()：将多行字符串转换为数组

# 将多行字符串转换为数组
string_to_array() {
    local -n arr_ref=$1
    local input=$2
    arr_ref=()
    while IFS= read -r line; do
        [ -n "$line" ] && arr_ref+=("$line")
    done <<< "$input"
}


