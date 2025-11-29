#!/bin/bash
# 清理删除函数

# 清理远程已删除的本地仓库
cleanup_deleted_repos() {
    local -n group_folders_ref=$1
    local -n sync_repos_map_ref=$2
    
    print_step "检查需要删除的本地仓库（远程已不存在）..."
    local delete_count=0
    
    # 获取仓库所有者（用于检查远程仓库是否存在）
    local repo_owner=$(get_github_username)
    if [ -n "$repo_owner" ]; then
        print_info "仓库所有者: $repo_owner"
    else
        print_warning "无法获取仓库所有者信息，将跳过远程仓库存在性检查"
    fi
    
    # 遍历所有分组文件夹
    local check_dirs=()
    for group_folder in "${!group_folders_ref[@]}"; do
        if [ -d "$group_folder" ]; then
            print_debug "检查分组文件夹: $group_folder"
            # 使用 nullglob 处理空目录情况
            shopt -s nullglob
            for dir in "$group_folder"/*; do
                [ -d "$dir" ] && check_dirs+=("$dir")
            done
            shopt -u nullglob
        fi
    done
    
    print_info "找到 ${#check_dirs[@]} 个本地目录需要检查"
    
    if [ ${#check_dirs[@]} -eq 0 ]; then
        print_info "没有需要检查的本地目录"
        CLEANUP_STATS_DELETE=0
        return 0
    fi
    
    echo ""
    # 遍历目录
    for local_dir in "${check_dirs[@]}"; do
        # 规范化路径（去除尾部斜杠）
        local normalized_dir="${local_dir%/}"
        
        # 跳过非目录或非 git 仓库
        [ ! -d "$normalized_dir" ] && continue
        [ ! -d "$normalized_dir/.git" ] && continue
        
        local repo_name=$(basename "$normalized_dir")
        local repo_path="$normalized_dir"
        
        print_debug "检查本地仓库: $repo_path"
        
        # 检查是否在要同步的仓库列表中
        if [ -z "${sync_repos_map_ref[$repo_path]}" ]; then
            # 如果不在要同步的分组中，检查是否在远程还存在
            if [ -n "$repo_owner" ]; then
                print_info "  检查远程仓库是否存在: $repo_owner/$repo_name"
                if gh repo view "$repo_owner/$repo_name" &>/dev/null; then
                    print_info "  仓库 $repo_name 还在远程，只是不在当前同步的分组中，保留"
                    continue
                else
                    print_warning "  仓库 $repo_name 在远程已不存在"
                fi
            else
                print_warning "  无法检查远程仓库状态，但仓库不在同步列表中"
            fi
            
            # 仓库已不存在，删除
            echo -n "[删除] $repo_path (远程仓库已不存在)... "
            print_info "  正在删除: $repo_path"
            local rm_output=$(rm -rf "$repo_path" 2>&1)
            local rm_exit=$?
            
            if [ $rm_exit -eq 0 ]; then
                echo "✓ 已删除"
                ((delete_count++))
                print_success "  已成功删除: $repo_path"
            else
                echo "✗ 删除失败"
                print_error "  删除失败: $repo_path"
                if [ -n "$rm_output" ]; then
                    print_error "  错误信息: $rm_output"
                fi
            fi
        else
            print_info "  仓库 $repo_name 在同步列表中，保留"
        fi
    done
    
    if [ $delete_count -eq 0 ]; then
        print_info "没有需要删除的本地仓库。"
    else
        echo ""
        print_info "已删除 $delete_count 个本地仓库（远程已不存在）。"
    fi
    
    CLEANUP_STATS_DELETE=$delete_count
}

