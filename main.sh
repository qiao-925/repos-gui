#!/bin/bash
# GitHub 仓库批量克隆脚本：极简设计，专注于核心功能
#
# 主要功能：
#   - 解析命令行参数（-t 并行任务数，-c 并行传输数）
#   - 读取并解析 REPO-GROUPS.md 配置文件
#   - 并行批量克隆所有仓库
#   - 输出最终统计报告
#
# 执行流程：
#   1. 解析命令行参数
#   2. 加载配置文件
#   3. 构建克隆任务列表
#   4. 并行执行克隆
#   5. 输出统计报告
#
# 特性：
#   - 双重并行：应用层并行（-t） + Git 层并行传输（-c）
#   - 直接覆盖：不检查仓库是否存在，直接克隆

set -euo pipefail

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 加载模块
source "${SCRIPT_DIR}/lib/logger.sh"
source "${SCRIPT_DIR}/lib/config.sh"
source "${SCRIPT_DIR}/lib/clone.sh"

# 默认参数
PARALLEL_TASKS=5      # 并行任务数（应用层）
PARALLEL_CONNECTIONS=8 # 并行传输数（Git 层）

# 任务列表文件（可选）
TASK_LIST_FILE=""     # 如果指定，从文件读取任务列表；否则从 REPO-GROUPS.md 解析
FAILED_REPOS_FILE="${SCRIPT_DIR}/failed-repos.txt"  # 失败列表文件

# 统计变量
TOTAL_REPOS=0
SUCCESS_COUNT=0
FAIL_COUNT=0
START_TIME=$(date +%s)

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -t|--tasks)
                PARALLEL_TASKS="$2"
                shift 2
                ;;
            -c|--connections)
                PARALLEL_CONNECTIONS="$2"
                shift 2
                ;;
            -f|--file)
                TASK_LIST_FILE="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 验证参数
    if ! [[ "$PARALLEL_TASKS" =~ ^[0-9]+$ ]] || [[ "$PARALLEL_TASKS" -lt 1 ]]; then
        log_error "并行任务数必须是正整数: $PARALLEL_TASKS"
        exit 1
    fi
    
    if ! [[ "$PARALLEL_CONNECTIONS" =~ ^[0-9]+$ ]] || [[ "$PARALLEL_CONNECTIONS" -lt 1 ]]; then
        log_error "并行传输数必须是正整数: $PARALLEL_CONNECTIONS"
        exit 1
    fi
}

# 显示帮助信息
show_help() {
    cat << EOF
GitHub 仓库批量克隆脚本

用法: $0 [选项]

选项:
  -t, --tasks NUM          并行任务数（同时克隆的仓库数量，默认: 5）
  -c, --connections NUM    并行传输数（每个仓库的 Git 连接数，默认: 8）
  -f, --file FILE          指定任务列表文件（格式：repo_full|repo_name|group_folder|group_name）
                           如果不指定，默认从 REPO-GROUPS.md 解析
  -h, --help               显示此帮助信息

示例:
  $0                        # 使用默认参数，从 REPO-GROUPS.md 解析所有仓库
  $0 -t 10 -c 16            # 并行任务数 10，并行传输数 16
  $0 -f failed-repos.txt    # 从失败列表文件重新执行失败的仓库
  $0 -f custom-list.txt     # 从自定义列表文件执行

任务列表文件格式（每行一个任务）:
  owner/repo|repo_name|group_folder|group_name

执行完成后，失败的仓库会自动保存到 failed-repos.txt
EOF
}

# 执行单个克隆任务（用于并行调用）
execute_clone_task() {
    # 在子shell中执行，禁用错误退出，避免影响主进程
    set +e
    local task="$1"
    local parallel_connections="$2"
    
    # 解析任务：repo_full|repo_name|group_folder|group_name
    IFS='|' read -r repo_full repo_name group_folder group_name <<< "$task"
    
    # 执行克隆，日志会直接输出
    if clone_repo "$repo_full" "$repo_name" "$group_folder" "$parallel_connections"; then
        return 0
    else
        return 1
    fi
}

# 并行执行克隆任务
execute_parallel_clone() {
    local tasks=("$@")
    local total="${#tasks[@]}"
    
    if [[ $total -eq 0 ]]; then
        log_warning "没有需要克隆的仓库"
        return 0
    fi
    
    log_info "开始批量克隆，共 $total 个仓库"
    log_info "并行任务数: $PARALLEL_TASKS, 并行传输数: $PARALLEL_CONNECTIONS"
    
    # 使用结果文件收集所有任务的结果
    # Windows 兼容：使用环境变量或项目目录
    local tmp_dir="${TMP:-${TEMP:-/tmp}}"
    if [[ ! -d "$tmp_dir" ]]; then
        tmp_dir="${SCRIPT_DIR}/.tmp"
        mkdir -p "$tmp_dir"
    fi
    local result_file="${tmp_dir}/clone_results_$$.txt"
    > "$result_file"  # 清空结果文件
    
    # 使用后台进程 + wait 实现并行控制
    local running=0
    local task_index=0
    local pids=()
    
    # 临时禁用错误退出，避免算术运算失败导致脚本退出
    set +e
    
    while [[ $task_index -lt $total ]] || [[ $running -gt 0 ]]; do
        # 启动新任务（如果还有未处理的任务且未达到并发限制）
        while [[ $running -lt $PARALLEL_TASKS ]] && [[ $task_index -lt $total ]]; do
            local task="${tasks[$task_index]}"
            
            # 在后台执行克隆任务
            # 使用子shell并禁用错误退出，避免后台进程错误导致主脚本退出
            # 直接执行，不使用命令替换，让 Git 的输出实时显示
            (
                set +e
                # 直接执行，输出直接到终端（实时显示）
                execute_clone_task "$task" "$PARALLEL_CONNECTIONS"
                local exit_code=$?
                # 只把结果写入文件
                if [[ $exit_code -eq 0 ]]; then
                    echo "SUCCESS" >> "$result_file"
                else
                    echo "FAIL" >> "$result_file"
                fi
            ) &
            
            local pid=$!
            pids+=("$pid")
            ((task_index++)) || true
            ((running++)) || true
        done
        
        # 检查已完成的任务
        local new_pids=()
        for pid in "${pids[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                new_pids+=("$pid")
            else
                # 任务完成
                wait "$pid" 2>/dev/null || true
                ((running--)) || running=0
            fi
        done
        pids=("${new_pids[@]}")
        
        # 短暂休眠，避免 CPU 占用过高
        sleep 0.1
    done
    
    # 等待所有任务完成
    for pid in "${pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
    
    # 恢复错误退出
    set -e
    
    # 统计结果并记录失败的仓库
    if [[ -f "$result_file" ]]; then
        > "$FAILED_REPOS_FILE"  # 清空失败列表
        local task_index=0
        while IFS= read -r result; do
            if [[ "$result" == "SUCCESS" ]]; then
                ((SUCCESS_COUNT++)) || true
            elif [[ "$result" == "FAIL" ]]; then
                ((FAIL_COUNT++)) || true
                # 记录失败的仓库到文件
                if [[ $task_index -lt $total ]]; then
                    echo "${tasks[$task_index]}" >> "$FAILED_REPOS_FILE"
                fi
            fi
            ((task_index++)) || true
        done < "$result_file"
        rm -f "$result_file"
        
        # 如果有失败的仓库，提示用户
        if [[ $FAIL_COUNT -gt 0 ]] && [[ -s "$FAILED_REPOS_FILE" ]]; then
            log_warning "有 $FAIL_COUNT 个仓库克隆失败"
            log_info "失败列表已保存到: $FAILED_REPOS_FILE"
            log_info "可以使用以下命令重新执行失败的仓库:"
            log_info "  bash main.sh -f $FAILED_REPOS_FILE"
        fi
    else
        log_warning "结果文件不存在: $result_file"
    fi
    
    log_info "并行克隆执行完成，成功: $SUCCESS_COUNT, 失败: $FAIL_COUNT"
}

# 输出最终统计
print_summary() {
    local end_time=$(date +%s)
    local duration=$((end_time - START_TIME))
    local hours=$((duration / 3600))
    local minutes=$(((duration % 3600) / 60))
    local seconds=$((duration % 60))
    
    echo ""
    log_info "========== 克隆完成 =========="
    log_info "总仓库数: $TOTAL_REPOS"
    log_success "成功: $SUCCESS_COUNT"
    
    if [[ $FAIL_COUNT -gt 0 ]]; then
        log_error "失败: $FAIL_COUNT"
    else
        log_info "失败: $FAIL_COUNT"
    fi
    
    log_info "耗时: ${hours}小时 ${minutes}分钟 ${seconds}秒"
    log_info "=============================="
}

# 主函数
main() {
    log_info "GitHub 仓库批量克隆脚本启动"
    
    # 解析命令行参数
    parse_args "$@"
    
    # 获取任务列表
    local tasks
    
    if [[ -n "$TASK_LIST_FILE" ]]; then
        # 从指定文件读取任务列表
        if [[ ! -f "$TASK_LIST_FILE" ]]; then
            log_error "任务列表文件不存在: $TASK_LIST_FILE"
            exit 1
        fi
        log_info "从文件读取任务列表: $TASK_LIST_FILE"
        mapfile -t tasks < "$TASK_LIST_FILE"
    else
        # 默认从配置文件解析
        log_info "解析配置文件: $CONFIG_FILE"
        mapfile -t tasks < <(parse_repo_groups)
    fi
    
    if [[ ${#tasks[@]} -eq 0 ]]; then
        log_error "未找到任何仓库任务"
        exit 1
    fi
    
    TOTAL_REPOS=${#tasks[@]}
    log_info "找到 $TOTAL_REPOS 个仓库任务"
    
    # 执行并行克隆
    execute_parallel_clone "${tasks[@]}"
    
    # 输出统计
    print_summary
    
    # 返回退出码
    if [[ $FAIL_COUNT -gt 0 ]]; then
        exit 1
    else
        exit 0
    fi
}

# 执行主函数
main "$@"

