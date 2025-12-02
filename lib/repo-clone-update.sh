#!/bin/bash
# 仓库克隆操作模块：提供优化的仓库克隆功能
#
# 主要功能：
#   - clone_repo()：克隆仓库（带自动重试和清理不完整目录）
#   - _execute_clone_cmd()：执行克隆命令（安全实现，避免使用 eval）
#
# 特性：
#   - 每个仓库克隆失败后立即重试3次（可配置间隔，默认3秒）
#   - 自动清理克隆失败的不完整目录
#   - 使用并行传输（--jobs）充分利用网络带宽，提高单个仓库的克隆速度
#   - 优先使用 SSH 协议（更快），失败时自动回退到 HTTPS
#   - 安全实现：使用命令数组替代 eval，避免命令注入风险
#   - 参考 Cursor IDE 的快速同步技术进行优化

# ========== 常量定义 ==========

# 重试配置
readonly CLONE_MAX_RETRIES=3
readonly CLONE_RETRY_INTERVAL=3  # 秒

# ========== 辅助函数 ==========

# 执行克隆命令（优化版：避免使用 eval，提高安全性）
# 参数：
#   $1: git_jobs（并行传输数）
#   $2: use_shallow_clone（是否使用浅克隆，0或1）
#   $3: repo_url（仓库URL）
#   $4: parent_dir（父目录路径）
#   $5: repo_name（仓库名称）
# 返回：
#   退出码
_execute_clone_cmd() {
    local git_jobs=$1
    local use_shallow_clone=$2
    local repo_url=$3
    local parent_dir=$4
    local repo_name=$5
    
    # 构建命令数组（更安全，避免 eval）
    local -a clone_args=(
        "git"
        "clone"
        "--jobs" "$git_jobs"
        "--progress"
    )
    
    if [ "$use_shallow_clone" -eq 1 ]; then
        clone_args+=("--depth" "1")
    fi
    
    clone_args+=("$repo_url" "$repo_name")
    
    # 在父目录中执行克隆命令
    (
        export GIT_PROGRESS_DELAY=0
        cd "$parent_dir" && "${clone_args[@]}" 2>&1
    )
}

# ========== 主要函数 ==========

# 克隆仓库（带自动重试和清理不完整目录）
clone_repo() {
    local repo=$1
    local repo_path=$2
    local current_index=$3
    local total_sync=$4
    local quiet_mode=${5:-0}
    
    # 使用全局常量
    local max_retries=$CLONE_MAX_RETRIES
    local retry_interval=$CLONE_RETRY_INTERVAL
    
    # 判断是否需要浅克隆（超过 300MB 的仓库使用浅克隆）
    local use_shallow_clone=0
    local repo_size_kb=0
    if [ -n "${global_repo_sizes[$repo]}" ]; then
        repo_size_kb="${global_repo_sizes[$repo]}"
        # 使用常量阈值判断是否需要浅克隆
        if [ "$repo_size_kb" -gt "$REPO_SIZE_LARGE_THRESHOLD" ]; then
            use_shallow_clone=1
        fi
    fi
    
    # 确保 SCRIPT_DIR 已定义（从 main.sh 导出）
    if [ -z "$SCRIPT_DIR" ]; then
        [ "$quiet_mode" -eq 0 ] && print_error "  错误: SCRIPT_DIR 未定义"
        return 1
    fi
    
    # 提前计算路径信息（避免在循环中重复计算）
    local parent_dir=$(dirname "$repo_path")
    local repo_name=$(basename "$repo_path")
    
    if [ "$quiet_mode" -eq 0 ]; then
        print_info "[$current_index/$total_sync] 正在克隆: $repo -> $parent_dir/..."
    fi
    
    # 创建父目录
    [ ! -d "$parent_dir" ] && mkdir -p "$parent_dir" && [ "$quiet_mode" -eq 0 ] && print_info "  已创建分组文件夹: $parent_dir"
    
    # 重试循环
    local retry_count=0
    local clone_exit_code=1
    local clone_duration=0
    
    while [ $retry_count -lt $max_retries ]; do
        # 如果之前尝试失败，清理不完整的目录
        if [ $retry_count -gt 0 ]; then
            if [ -d "$repo_path" ] && [ ! -d "$repo_path/.git" ]; then
                # 目录存在但不是完整仓库，删除
                [ "$quiet_mode" -eq 0 ] && print_info "  清理不完整的目录: $repo_path"
                rm -rf "$repo_path" 2>/dev/null || true
            fi
            [ "$quiet_mode" -eq 0 ] && print_info "  [重试 $retry_count/$((max_retries - 1))] 等待 ${retry_interval} 秒后重试..."
            sleep "$retry_interval"
        fi
        
        # 克隆仓库（gh repo clone 需要在父目录执行，不能使用通用函数）
        if [ "$quiet_mode" -eq 0 ]; then
            if [ $retry_count -eq 0 ]; then
                print_info "🌐 [外部调用] 开始: 克隆仓库 $repo 到 $repo_path"
            else
                print_info "🌐 [外部调用] 重试: 克隆仓库 $repo 到 $repo_path (第 $retry_count 次重试)"
            fi
        fi
        
        local clone_start_time=$(date +%s)
        
        # 优化克隆策略：使用 Git 原生命令 + 并行传输
        # 参考 Cursor 的快速同步技术：
        # 1. 使用并行传输（--jobs）充分利用网络带宽，提高单个仓库的克隆速度
        # 2. 直接使用 git clone 可能比 gh repo clone 更快
        # 3. 优先使用 SSH 协议（更快），失败时回退到 HTTPS
        #
        # 并行传输说明：
        #   --jobs 参数让 Git 在克隆单个仓库时，使用多个并行连接同时传输数据
        #   例如：--jobs 8 表示使用 8 个并行连接来传输该仓库的对象
        #   这样可以充分利用网络带宽，特别是在高带宽环境下效果明显
        #   注意：这与脚本层面的并行任务（同时克隆多个仓库）是不同的概念
        
        # 获取并行传输数（从环境变量 GIT_CLONE_JOBS 读取，默认 8）
        local git_jobs=${GIT_CLONE_JOBS:-8}
        
        # 构建仓库 URL（优先使用 SSH，回退到 HTTPS）
        local repo_url=""
        # 检查是否配置了 SSH
        if [ -f ~/.ssh/id_rsa ] || [ -f ~/.ssh/id_ed25519 ] || [ -f ~/.ssh/id_ecdsa ]; then
            # 尝试使用 SSH URL（更快）
            repo_url="git@github.com:$repo.git"
            [ "$quiet_mode" -eq 0 ] && print_info "  使用 SSH 协议克隆（检测到 SSH 密钥）"
        else
            # 使用 HTTPS URL
            repo_url="https://github.com/$repo.git"
            [ "$quiet_mode" -eq 0 ] && print_info "  使用 HTTPS 协议克隆（未检测到 SSH 密钥）"
        fi
        
        # 执行优化克隆（使用并行传输）
        # 注意：Git 2.32+ 才支持 --jobs 参数，如果版本过低会自动忽略
        # 对于大仓库（>300MB），使用浅克隆（--depth 1）以节省空间和时间
        # 显示浅克隆提示
        if [ "$use_shallow_clone" -eq 1 ] && [ "$quiet_mode" -eq 0 ]; then
            local size_display=$(format_repo_size "$repo_size_kb")
            print_info "  使用浅克隆（仓库大小: $size_display，仅克隆最新提交）"
        fi
        
        # 执行克隆命令
        _execute_clone_cmd "$git_jobs" "$use_shallow_clone" "$repo_url" "$parent_dir" "$repo_name"
        
        clone_exit_code=$?
        
        # 如果 SSH 克隆失败，尝试使用 HTTPS
        if [ "$clone_exit_code" -ne 0 ] && [[ "$repo_url" == git@* ]]; then
            [ "$quiet_mode" -eq 0 ] && print_warning "  SSH 克隆失败（退出码: $clone_exit_code），回退到 HTTPS 协议..."
            repo_url="https://github.com/$repo.git"
            
            # 重新执行克隆命令（HTTPS 回退时也使用相同的浅克隆策略）
            _execute_clone_cmd "$git_jobs" "$use_shallow_clone" "$repo_url" "$parent_dir" "$repo_name"
            
            clone_exit_code=$?
            
            if [ "$clone_exit_code" -eq 0 ]; then
                [ "$quiet_mode" -eq 0 ] && print_info "  HTTPS 克隆成功"
            fi
        fi
        
        local clone_end_time=$(date +%s)
        clone_duration=$((clone_end_time - clone_start_time))
        
        if [ "$clone_exit_code" -eq 0 ]; then
            # 克隆成功
            if [ "$quiet_mode" -eq 0 ]; then
                if [ $retry_count -eq 0 ]; then
                    print_success "✅ [外部调用] 完成: 克隆仓库 $repo (耗时: ${clone_duration}秒)"
                else
                    print_success "✅ [外部调用] 重试成功: 克隆仓库 $repo (耗时: ${clone_duration}秒, 重试 $retry_count 次)"
                fi
                print_success "  克隆成功: $repo_path (耗时: ${clone_duration}秒)"
            fi
            return 0
        else
            # 克隆失败
            if [ "$quiet_mode" -eq 0 ]; then
                if [ $retry_count -eq 0 ]; then
                    print_error "❌ [外部调用] 失败: 克隆仓库 $repo (耗时: ${clone_duration}秒, 退出码: $clone_exit_code)"
                else
                    print_error "❌ [外部调用] 重试失败: 克隆仓库 $repo (耗时: ${clone_duration}秒, 退出码: $clone_exit_code, 第 $retry_count 次重试)"
                fi
            fi
        fi
        
        ((retry_count++))
    done
    
    # 所有重试都失败，清理不完整的目录
    if [ -d "$repo_path" ] && [ ! -d "$repo_path/.git" ]; then
        [ "$quiet_mode" -eq 0 ] && print_info "  清理不完整的目录: $repo_path"
        rm -rf "$repo_path" 2>/dev/null || true
    fi
    
    # 记录错误
    local error_msg="克隆失败，已重试 $((max_retries - 1)) 次，退出代码: $clone_exit_code"
    [ "$quiet_mode" -eq 0 ] && print_error "  克隆失败: $error_msg"
    [ "$quiet_mode" -eq 0 ] && print_error "  请查看上方的错误信息"
    return 1
}


