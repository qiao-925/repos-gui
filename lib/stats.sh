#!/bin/bash
# 统计和报告模块：提供克隆操作的统计功能
#
# 主要功能：
#   - init_sync_stats()：初始化全局统计变量
#   - update_sync_statistics()：更新统计信息（成功/失败计数）
#   - print_final_summary()：输出最终统计报告
#
# 统计内容：
#   - 成功/失败计数
#   - 耗时统计

# 初始化全局统计变量
init_sync_stats() {
    declare -g SYNC_STATS_SUCCESS=0
    declare -g SYNC_STATS_FAIL=0
    declare -gA group_names
    
    # 耗时统计
    declare -g SYNC_START_TIME=$(date +%s)  # 克隆开始时间
}

# 更新统计信息
update_sync_statistics() {
    local result=$1
    
    if [ "$result" -eq 0 ]; then
        # 克隆成功
        ((SYNC_STATS_SUCCESS++))
    else
        # 克隆失败
        ((SYNC_STATS_FAIL++))
    fi
}

# 格式化时间（秒转换为可读格式）
_format_duration() {
    local seconds=$1
    if [ "$seconds" -lt 60 ]; then
        echo "${seconds}秒"
    elif [ "$seconds" -lt 3600 ]; then
        local mins=$((seconds / 60))
        local secs=$((seconds % 60))
        echo "${mins}分${secs}秒"
    else
        local hours=$((seconds / 3600))
        local mins=$(((seconds % 3600) / 60))
        local secs=$((seconds % 60))
        echo "${hours}小时${mins}分${secs}秒"
    fi
}

# 输出最终统计信息
print_final_summary() {
    local sync_end_time=$(date +%s)
    local total_duration=$((sync_end_time - ${SYNC_START_TIME:-$sync_end_time}))
    
    echo ""
    echo "=================================================="
    echo "✅ 克隆完成！"
    echo "=================================================="
    echo "📊 统计信息："
    echo "  成功: ${SYNC_STATS_SUCCESS:-0}"
    echo "  失败: ${SYNC_STATS_FAIL:-0}"
    echo ""
    echo "⏱️  耗时统计："
    echo "  总耗时: $(_format_duration $total_duration)"
    echo ""
    echo "=================================================="
}



