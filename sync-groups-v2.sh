#!/bin/bash
# GitHub 仓库按分组同步脚本

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/lib"

# 加载基础模块（所有情况都需要）
source "$LIB_DIR/config.sh"
source "$LIB_DIR/logger.sh"
source "$LIB_DIR/parser.sh"

# 主函数
main() {
    # 0. 特殊参数处理：--list 或 -l 直接列出分组并退出（只加载必要模块）
    if [ $# -eq 0 ] || [ "$1" = "--list" ] || [ "$1" = "-l" ]; then
        list_groups
        exit 0
    fi
    
    # 加载其他模块（同步操作需要）
    source "$LIB_DIR/github.sh"
    source "$LIB_DIR/sync.sh"
    source "$LIB_DIR/cleanup.sh"
    source "$LIB_DIR/stats.sh"
    source "$LIB_DIR/retry.sh"
    source "$LIB_DIR/main_helpers.sh"
    
    # 1. 参数解析
    local parsed_args_output=$(parse_arguments "$@")
    local parsed_exit_code=$?
    
    if [ $parsed_exit_code -ne 0 ]; then
        exit $parsed_exit_code
    fi
    
    # 将解析后的参数转换为数组
    local groups_array=()
    while IFS= read -r line; do
        [ -n "$line" ] && groups_array+=("$line")
    done <<< "$parsed_args_output"
    
    # 2. 初始化同步环境
    initialize_sync
    
    # 3. 执行同步
    execute_sync "${groups_array[@]}"
    
    # 4. 构建同步仓库映射（用于清理检查）
    declare -A sync_repos_map
    build_sync_repos_map sync_repos_map
    
    # 5. 清理删除远程已不存在的本地仓库
    cleanup_deleted_repos group_folders sync_repos_map
    
    # 6. 输出最终统计
    print_final_summary
    
    # 7. 显示失败仓库详情
    if [ -n "$ALL_FAILED_LOGS_ARRAY" ]; then
        local -n failed_logs=$ALL_FAILED_LOGS_ARRAY
        print_failed_repos_details failed_logs
    fi
}

# 执行主函数
main "$@"
