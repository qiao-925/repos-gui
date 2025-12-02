#!/bin/bash
# 差异分析模块：扫描和分析远程与本地仓库的差异
#
# 主要功能：
#   - scan_global_diff()：全局扫描差异，找出缺失的仓库（只检查缺失，不检查更新）
#
# 执行流程：
#   1. 遍历所有分组和仓库
#   2. 检查每个仓库的本地状态（检查 .git 目录）
#   3. 分类：缺失 / 已存在（跳过）/ 跳过 / 不存在
#   4. 存储到全局数组 global_repos_to_clone
#
# 特性：
#   - 只检查缺失，不检查更新（符合单一职责原则）
#   - 使用缓存优化性能
#   - 实时显示扫描进度

# 全局变量声明（在函数外部声明，确保全局可见）
declare -gA global_repos_to_clone  # key: group_folder, value: "repo_full|repo_name repo_full|repo_name ..."
declare -gA global_repo_sizes      # key: repo_full, value: size_kb

# 全局扫描差异：找出所有缺失的仓库（只检查缺失，不检查更新）
scan_global_diff() {
    local groups=("$@")
    
    print_step "全局扫描差异，找出缺失的仓库..."
    echo ""
    
    local total_missing=0
    local total_skipped=0
    local total_not_found=0
    
    # 计算总仓库数（用于显示进度）
    local total_repos=0
    for input_group in "${groups[@]}"; do
        local group_name=$(find_group_name "$input_group")
        if [ -z "$group_name" ]; then
            continue
        fi
        local group_repos=$(get_group_repos "$group_name")
        if [ -z "$group_repos" ]; then
            continue
        fi
        local repos_array
        string_to_array repos_array "$group_repos"
        total_repos=$((total_repos + ${#repos_array[@]}))
    done
    
    print_info "📋 共需要检查 $total_repos 个仓库，开始扫描..."
    echo ""
    
    local current_repo_index=0
    local group_index=0
    
    # 遍历所有分组，收集缺失和更新的仓库
    for input_group in "${groups[@]}"; do
        local group_name=$(find_group_name "$input_group")
        
        if [ -z "$group_name" ]; then
            continue
        fi
        
        ((group_index++))
        local group_folder=$(get_group_folder "$group_name")
        local group_repos=$(get_group_repos "$group_name")
        
        if [ -z "$group_repos" ]; then
            continue
        fi
        
        # 创建分组文件夹（如果不存在）
        if [ ! -d "$group_folder" ]; then
            mkdir -p "$group_folder"
        fi
        
        # 注册分组名称映射
        group_names["$group_folder"]="$group_name"
        
        local repos_array
        string_to_array repos_array "$group_repos"
        
        local group_missing=()
        
        print_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_info "检查分组 [$group_index/${#groups[@]}]: $group_name (${#repos_array[@]} 个仓库)"
        print_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        # 检查每个仓库的状态
        for repo_name in "${repos_array[@]}"; do
            if [ -z "$repo_name" ]; then
                continue
            fi
            
            ((current_repo_index++))
            
            # 显示检查进度
            echo -n "  [$current_repo_index/$total_repos] 检查: $repo_name ... " >&2
            
            # 查找仓库完整名称
            local repo_full=$(find_repo_full_name "$repo_name")
            
            if [ -z "$repo_full" ]; then
                echo "❌ 远程不存在" >&2
                ((total_not_found++))
                continue
            fi
            
            local repo_path="$group_folder/$repo_name"
            
            # 检查仓库是否存在
            if [ -d "$repo_path/.git" ]; then
                # 已存在 git 仓库，跳过
                echo "✅ 已存在 (跳过)" >&2
            elif [ -d "$repo_path" ]; then
                # 目录存在但不是 git 仓库，跳过
                echo "⚠️  目录存在但非 git 仓库 (跳过)" >&2
                ((total_skipped++))
                continue
            else
                # 新仓库，加入缺失列表
                # 获取仓库大小（用于统计和浅克隆决策）
                local repo_size_kb=$(get_repo_size "$repo_full")
                if [ "$repo_size_kb" -gt 0 ]; then
                    global_repo_sizes["$repo_full"]="$repo_size_kb"
                    local size_display=$(format_repo_size "$repo_size_kb")
                    echo "🔴 缺失 (需克隆, 大小: $size_display)" >&2
                else
                    echo "🔴 缺失 (需克隆)" >&2
                fi
                group_missing+=("$repo_full|$repo_name")
                ((total_missing++))
            fi
        done
        
        # 显示分组统计
        echo "" >&2
        if [ ${#group_missing[@]} -gt 0 ]; then
            print_info "  分组 '$group_name' 统计："
            print_warning "    - 缺失: ${#group_missing[@]} 个"
        fi
        echo "" >&2
        
        # 存储到全局数组
        if [ ${#group_missing[@]} -gt 0 ]; then
            global_repos_to_clone["$group_folder"]=$(printf '%s\n' "${group_missing[@]}")
        fi
    done
    
    echo ""
    echo "=================================================="
    print_info "📊 全局差异分析完成"
    echo "=================================================="
    echo ""
    print_info "总体统计："
    echo "  - 检查的仓库总数: $total_repos"
    echo "  - 🔴 缺失的仓库（需要克隆）: $total_missing 个"
    if [ "$total_skipped" -gt 0 ]; then
        echo "  - ⚠️  跳过的仓库（非 git 仓库）: $total_skipped 个"
    fi
    if [ "$total_not_found" -gt 0 ]; then
        echo "  - ❌ 远程不存在的仓库: $total_not_found 个"
    fi
    echo ""
    
    # 显示仓库大小统计
    if [ "$total_missing" -gt 0 ] && [ ${#global_repo_sizes[@]} -gt 0 ]; then
        print_info "📦 仓库大小统计："
        
        # 计算总大小
        local total_size_kb=0
        local large_repos=0  # 超过 300MB 的仓库数（将使用浅克隆）
        local huge_repos=0   # 超过 1GB 的仓库数
        
        for repo_full in "${!global_repo_sizes[@]}"; do
            local size_kb="${global_repo_sizes[$repo_full]}"
            total_size_kb=$((total_size_kb + size_kb))
            
            # 统计大仓库（使用常量阈值）
            if [ "$size_kb" -gt "$REPO_SIZE_LARGE_THRESHOLD" ]; then
                ((large_repos++))
            fi
            
            # 统计超大仓库（使用常量阈值）
            if [ "$size_kb" -gt "$REPO_SIZE_HUGE_THRESHOLD" ]; then
                ((huge_repos++))
            fi
        done
        
        local total_size_display=$(format_repo_size "$total_size_kb")
        echo "  - 总大小: $total_size_display"
        
        if [ "$large_repos" -gt 0 ]; then
            echo "  - ⚠️  超过 300MB 的仓库: $large_repos 个（将使用浅克隆）"
        fi
        
        if [ "$huge_repos" -gt 0 ]; then
            echo "  - 🔴 超过 1GB 的仓库: $huge_repos 个"
        fi
        
        # 显示前 5 大仓库
        if [ ${#global_repo_sizes[@]} -gt 0 ]; then
            echo ""
            print_info "前 5 大仓库："
            # 构建排序数组（格式：size_kb|repo_full）
            local -a sorted_repos=()
            for repo_full in "${!global_repo_sizes[@]}"; do
                local size_kb="${global_repo_sizes[$repo_full]}"
                sorted_repos+=("${size_kb}|${repo_full}")
            done
            # 按大小降序排序（数值排序）
            IFS=$'\n' sorted_repos=($(printf '%s\n' "${sorted_repos[@]}" | sort -t'|' -k1 -rn))
            local count=0
            for repo_info in "${sorted_repos[@]}"; do
                IFS='|' read -r size_kb repo_full <<< "$repo_info"
                local size_display=$(format_repo_size "$size_kb")
                local repo_name=$(basename "$repo_full")
                echo "  $((++count)). $repo_name - $size_display"
                [ $count -ge 5 ] && break
            done
        fi
        echo ""
    fi
    
    if [ "$total_missing" -gt 0 ]; then
        print_warning "⚠️  发现 $total_missing 个缺失的仓库，将开始批量克隆"
    else
        print_info "✅ 所有仓库已存在，无需克隆"
    fi
    echo ""
}


