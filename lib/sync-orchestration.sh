#!/bin/bash
# 克隆编排模块：负责 GitHub 仓库的批量克隆操作
#
# 主要功能：
#   - initialize_sync()：初始化克隆环境（检查配置、创建目录、初始化连接）
#   - execute_sync()：执行批量克隆操作（默认并行，高性能）
#   - execute_parallel_repo_tasks()：并行执行仓库任务
#
# 执行流程：
#   1. 扫描所有分组，找出缺失的仓库（由 diff-analysis.sh 提供）
#   2. 批量克隆所有缺失的仓库（并行处理）
#
# 特性：
#   - 默认并行处理（同时处理多个仓库，充分利用网络带宽和设备性能）
#   - 并行任务数可通过 PARALLEL_JOBS 环境变量配置（默认 5）
#   - 实时进度显示
#   - 每个仓库失败后立即重试3次（带间隔）

# ============================================================================
# 常量定义
# ============================================================================

# 并行执行时的等待时间（秒）
readonly PARALLEL_WAIT_LONG=0.5   # 达到并发上限时的等待时间
readonly PARALLEL_WAIT_SHORT=0.1  # 未达到并发上限时的等待时间

# ============================================================================
# 通用并行执行函数
# ============================================================================

# 执行并行仓库任务（克隆）
# 参数:
#   $1: 任务数组名（引用，格式：repo_full|repo_name|group_folder|group_name|global_index）
#   $2: 总任务数
#   $3: 成功消息模板（如 "所有缺失仓库克隆完成"）
#   $4: 并行任务数（PARALLEL_JOBS）
execute_parallel_repo_tasks() {
    local -n tasks_ref=$1
    local total_count=$2
    local success_msg=$3
    local parallel_jobs=$4
    local task_type="clone"  # 固定为克隆
    
    if [ ${#tasks_ref[@]} -eq 0 ]; then
        return 0
    fi
    
    local task_index=0
    local temp_dir
    temp_dir=$(mktemp -d) || {
        print_error "无法创建临时目录"
        return 1
    }
    local -a job_pids=()
    
    print_info "开始并行克隆（并发数: $parallel_jobs）..."
    echo ""
    
    # 并行执行任务（优化版：清理已完成的进程ID，减少轮询开销）
    while [ $task_index -lt ${#tasks_ref[@]} ] || [ ${#job_pids[@]} -gt 0 ]; do
        # 启动新任务（直到达到并发上限）
        while [ ${#job_pids[@]} -lt $parallel_jobs ] && [ $task_index -lt ${#tasks_ref[@]} ]; do
            local task_info="${tasks_ref[$task_index]}"
            IFS='|' read -r repo_full repo_name group_folder group_name global_index <<< "$task_info"
            
            local repo_path="$group_folder/$repo_name"
            local log_file="$temp_dir/${task_type}_${task_index}.log"
            
            # 后台执行任务
            (
                local repo_full_var="$repo_full"
                local repo_path_var="$repo_path"
                local repo_name_var="$repo_name"
                local group_name_var="$group_name"
                local global_index_var="$global_index"
                local total_count_var="$total_count"
                
                update_progress_line "[$global_index_var/$total_count_var] 开始克隆: $repo_name_var (分组: $group_name_var)"
                
                {
                    local task_start_time=$(date +%s)
                    clone_repo "$repo_full_var" "$repo_path_var" "$global_index_var" "$total_count_var" 1 2>&1 | \
                        tee -a "$log_file" >&2
                    local result=${PIPESTATUS[0]}
                    local task_end_time=$(date +%s)
                    local task_duration=$((task_end_time - task_start_time))
                    echo "result:$result" >> "$log_file"
                    
                    if [ "$result" -ne 0 ]; then
                        update_progress_line "[$global_index_var/$total_count_var] 克隆失败: $repo_name_var ✗ (耗时: ${task_duration}秒)"
                    else
                        update_progress_line "[$global_index_var/$total_count_var] 克隆完成: $repo_name_var ✓ (耗时: ${task_duration}秒)"
                    fi
                } >&2
            ) &
            
            local pid=$!
            job_pids+=($pid)
            ((task_index++))
        done
        
        # 清理已完成的进程ID并等待（优化：减少轮询频率）
        if [ ${#job_pids[@]} -gt 0 ]; then
            # 清理已完成的进程ID（只保留活跃的）
            local -a new_job_pids=()
            for pid in "${job_pids[@]}"; do
                if kill -0 "$pid" 2>/dev/null; then
                    new_job_pids+=($pid)
                fi
            done
            job_pids=("${new_job_pids[@]}")
            
            # 如果还有活跃任务且未达到并发上限，短暂等待后继续
            # 如果达到并发上限，等待更长时间（让任务有时间完成）
            if [ ${#job_pids[@]} -ge $parallel_jobs ] && [ $task_index -lt ${#tasks_ref[@]} ]; then
                # 达到并发上限，等待更长时间（让任务有时间完成）
                sleep "$PARALLEL_WAIT_LONG"
            elif [ ${#job_pids[@]} -gt 0 ]; then
                # 还有活跃任务但未达到上限，短暂等待（避免 CPU 空转）
                sleep "$PARALLEL_WAIT_SHORT"
            fi
        fi
    done
    
    # 等待所有任务完成
    for pid in "${job_pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
    
    # 汇总结果
    for log_file in "$temp_dir"/${task_type}_*.log; do
        if [ -f "$log_file" ]; then
            local result=$(grep "^result:" "$log_file" | sed 's/^result://' || echo "1")
            update_sync_statistics "$result"
        fi
    done
    
    rm -rf "$temp_dir"
    
    echo ""
    print_success "$success_msg（$total_count 个）"
    echo ""
}

# ============================================================================
# 核心功能函数
# ============================================================================


# 初始化克隆环境
initialize_sync() {
    # 检查配置文件
    print_step "检查配置文件..."
    if [ ! -f "$CONFIG_FILE" ]; then
        print_error "分类文档不存在: $CONFIG_FILE"
        print_info "请参考 README.md 中的使用流程创建分类文档"
        print_info "或使用 'GitHub 仓库分类 Prompt.md' 中的 prompt 让 AI 生成"
        exit 1
    fi
    print_success "配置文件存在: $CONFIG_FILE"
    
    # 创建 repos 目录（如果不存在）
    # 注意：REPOS_DIR 在 config.sh 中定义
    if [ ! -d "$REPOS_DIR" ]; then
        mkdir -p "$REPOS_DIR"
        print_info "已创建 $REPOS_DIR 目录"
    fi
    
    # 初始化 GitHub 连接
    init_github_connection
    
    # 显示克隆信息
    echo "=================================================="
    echo "GitHub 仓库批量克隆工具"
    echo "=================================================="
    echo ""
    
    # 初始化统计变量
    init_sync_stats
}



# 执行批量克隆操作（遍历所有分组）- 默认并行，高性能
execute_sync() {
    local groups=("$@")
    
    # 并行任务数配置（默认 5，可通过命令行参数或环境变量 PARALLEL_JOBS 配置）
    local PARALLEL_JOBS=${PARALLEL_JOBS:-5}
    # 并行传输数配置（默认 8，可通过命令行参数或环境变量 GIT_CLONE_JOBS 配置）
    local GIT_CLONE_JOBS=${GIT_CLONE_JOBS:-8}
    
    print_info "📊 并行处理模式："
    print_info "   - 并行任务数：$PARALLEL_JOBS（同时克隆 $PARALLEL_JOBS 个仓库）"
    print_info "   - 并行传输数：$GIT_CLONE_JOBS（每个仓库使用 $GIT_CLONE_JOBS 个连接）"
    print_info "💡 提示：可通过 -t N 设置并行任务数，-c N 设置并行传输数"
    echo ""
    
    
    # 处理所有分组的缺失仓库（需要克隆的）
    local total_missing_count=0
    for group_folder in "${!global_repos_to_clone[@]}"; do
        local repos_list="${global_repos_to_clone[$group_folder]}"
        if [ -n "$repos_list" ]; then
            local repos_array
            string_to_array repos_array "$repos_list"
            total_missing_count=$((total_missing_count + ${#repos_array[@]}))
        fi
    done
    
    if [ "$total_missing_count" -gt 0 ]; then
        print_step "批量克隆所有缺失的仓库（共 $total_missing_count 个）..."
        echo ""
        
        # 收集所有需要克隆的仓库信息（用于并行处理）
        local -a all_clone_tasks=()
        local global_index=0
        
        for group_folder in "${!global_repos_to_clone[@]}"; do
            local group_name="${group_names[$group_folder]}"
            local repos_list="${global_repos_to_clone[$group_folder]}"
            
            if [ -z "$repos_list" ]; then
                continue
            fi
            
            local repos_array
            string_to_array repos_array "$repos_list"
            
            for repo_info in "${repos_array[@]}"; do
                ((global_index++))
                # 格式：repo_full|repo_name|group_folder|group_name|global_index
                IFS='|' read -r repo_full repo_name <<< "$repo_info"
                all_clone_tasks+=("$repo_full|$repo_name|$group_folder|$group_name|$global_index")
            done
        done
        
        # 使用并行执行函数（注意：重试机制在 clone_repo 内部实现）
        execute_parallel_repo_tasks all_clone_tasks "$total_missing_count" \
            "所有缺失仓库克隆完成" "$PARALLEL_JOBS"
    else
        print_info "所有仓库已存在，无需克隆"
    fi
    
}

