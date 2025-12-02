#!/bin/bash
# GitHub 仓库批量克隆工具 - 主入口
#
# 核心功能：
#   - 批量克隆：从配置文件读取仓库列表，批量克隆到本地
#   - 并发控制：通过 -t N 参数控制并行任务数（默认5）
#   - 并行传输：通过 -c N 参数控制每个仓库的并行连接数（默认8）
#   - 智能重试：每个仓库克隆失败后立即重试3次（带间隔）
#   - 自动清理：克隆失败后自动删除不完整的目录
#   - 二次执行：已存在的仓库自动跳过，只克隆缺失的

# ============================================
# 配置和常量定义
# ============================================
readonly CONFIG_FILE="REPO-GROUPS.md"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly GIT_CLONE_JOBS_MAX=64  # 并行传输数最大值

# 切换到脚本目录，确保相对路径正确
cd "$SCRIPT_DIR" || {
    echo "错误: 无法切换到脚本目录: $SCRIPT_DIR" >&2
    exit 1
}

# 导出变量供其他模块使用
export SCRIPT_DIR
export CONFIG_FILE
# 注意：REPOS_DIR 在 config.sh 中定义，加载 config.sh 后可用

# ============================================
# 加载所有模块
# ============================================
# 按依赖顺序加载模块
source "$SCRIPT_DIR/lib/logger.sh"      # 日志输出（无依赖）
source "$SCRIPT_DIR/lib/utils.sh"       # 工具函数（无依赖）
source "$SCRIPT_DIR/lib/progress.sh"    # 进度显示（无依赖）
source "$SCRIPT_DIR/lib/config.sh"      # 配置解析（依赖 logger, utils）
source "$SCRIPT_DIR/lib/cache.sh"       # 缓存初始化（依赖 logger, config）
source "$SCRIPT_DIR/lib/github-api-query.sh"      # GitHub API 查询（依赖 logger）
source "$SCRIPT_DIR/lib/repo-clone-update.sh"     # 仓库克隆操作（依赖 logger, github-api-query, utils）
source "$SCRIPT_DIR/lib/stats.sh"                 # 统计和错误记录（依赖 logger）
source "$SCRIPT_DIR/lib/diff-analysis.sh"         # 差异分析（依赖 logger, github-api-query, cache, config）
source "$SCRIPT_DIR/lib/sync-orchestration.sh"    # 克隆编排和策略（依赖所有其他模块）

# ============================================
# 命令行参数解析
# ============================================

parse_args() {
    # 默认值
    PARALLEL_JOBS=${PARALLEL_JOBS:-5}      # 并行任务数（同时克隆多少个仓库）
    GIT_CLONE_JOBS=${GIT_CLONE_JOBS:-8}   # 并行传输数（每个仓库克隆时使用多少个连接）
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -t)
                if [[ -n "$2" && "$2" =~ ^[0-9]+$ ]]; then
                    PARALLEL_JOBS="$2"
                    shift 2
                else
                    print_error "-t 需要指定一个数字"
                    print_info "用法: -t <数字>"
                    exit 1
                fi
                ;;
            -c)
                if [[ -n "$2" && "$2" =~ ^[0-9]+$ ]]; then
                    GIT_CLONE_JOBS="$2"
                    shift 2
                else
                    print_error "-c 需要指定一个数字"
                    print_info "用法: -c <数字>"
                    exit 1
                fi
                ;;
            --help|-h)
                echo "用法: $0 [选项]"
                echo ""
                echo "选项:"
                echo "  -t <数字>  设置并行任务数（同时克隆多少个仓库，默认: 5）"
                echo "  -c <数字>  设置并行传输数（每个仓库克隆时的连接数，默认: 8）"
                echo "  --help, -h  显示此帮助信息"
                echo ""
                echo "说明:"
                echo "  -t 参数：控制脚本层面的并行度（同时克隆多少个不同的仓库）"
                echo "  -c 参数：控制 Git 层面的并行度（单个仓库克隆时使用多少个连接）"
                echo "  两者可以叠加使用，效果更佳"
                echo ""
                echo "示例:"
                echo "  $0              # 使用默认值（-t 5, -c 8）"
                echo "  $0 -t 10        # 同时克隆 10 个仓库，每个使用 8 个连接"
                echo "  $0 -c 16        # 同时克隆 5 个仓库，每个使用 16 个连接"
                echo "  $0 -t 10 -c 16  # 同时克隆 10 个仓库，每个使用 16 个连接"
                exit 0
                ;;
            *)
                print_error "未知参数: $1"
                print_info "使用 --help 查看帮助信息"
                exit 1
                ;;
        esac
    done
    
    # 验证并行任务数是否为有效数字
    if ! [[ "$PARALLEL_JOBS" =~ ^[0-9]+$ ]] || [ "$PARALLEL_JOBS" -lt 1 ]; then
        print_error "并行任务数必须是大于 0 的整数，当前值: $PARALLEL_JOBS"
        exit 1
    fi
    
    # 验证并行传输数是否为有效数字
    if ! [[ "$GIT_CLONE_JOBS" =~ ^[0-9]+$ ]] || [ "$GIT_CLONE_JOBS" -lt 1 ]; then
        print_error "并行传输数必须是大于 0 的整数，当前值: $GIT_CLONE_JOBS"
        exit 1
    fi
    
    # 限制并行传输数最大值（高带宽环境可以支持更多连接）
    if [ "$GIT_CLONE_JOBS" -gt "$GIT_CLONE_JOBS_MAX" ]; then
        print_warning "并行传输数过大（$GIT_CLONE_JOBS），已限制为 $GIT_CLONE_JOBS_MAX"
        GIT_CLONE_JOBS=$GIT_CLONE_JOBS_MAX
    fi
    
    # 导出为环境变量，供后续模块使用
    export PARALLEL_JOBS
    export GIT_CLONE_JOBS
}

# ============================================
# 主函数
# ============================================

main() {
    # 0. 解析命令行参数
    parse_args "$@"
    
    # 1. 初始化同步环境
    initialize_sync || exit 1
    
    # 2. 初始化所有缓存（性能优化：一次性加载所有数据，避免重复文件系统遍历）
    echo ""
    print_step "初始化缓存系统..."
    init_config_cache || exit 1
    init_repo_cache || exit 1
    echo ""
    
    # 3. 获取所有分组用于克隆（使用缓存）
    print_info "准备克隆所有分组..."
    local all_groups=$(get_all_group_names)
    if [ -z "$all_groups" ]; then
        print_error "无法读取分组列表"
        exit 1
    fi
    
    local groups_array
    string_to_array groups_array "$all_groups"
    
    if [ ${#groups_array[@]} -eq 0 ]; then
        print_error "配置文件中没有找到任何分组"
        exit 1
    fi
    
    print_info "找到 ${#groups_array[@]} 个分组，开始克隆..."
    echo ""
    
    # 5. 全局扫描差异，找出缺失的仓库（只检查缺失，不检查更新）
    scan_global_diff "${groups_array[@]}" || exit 1
    
    # 6. 执行批量克隆（只处理缺失的仓库）
    execute_sync "${groups_array[@]}" || exit 1
    
    # 7. 输出最终统计
    print_final_summary
}

# 执行主函数（参数已在 parse_args 中处理）
main "$@"

