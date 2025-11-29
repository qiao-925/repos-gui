#!/bin/bash
# 配置文件解析函数

# 配置缓存（避免重复读取文件）
declare -A _CONFIG_GROUPS=()      # 分组名 -> 别名映射
declare -A _CONFIG_GROUP_REPOS=() # 分组名 -> 仓库数组（用换行符分隔）
_CONFIG_LOADED=false

# 加载并缓存配置文件
load_config_cache() {
    if [ "$_CONFIG_LOADED" = "true" ]; then
        print_info "配置文件已缓存，跳过重新加载"
        return 0
    fi
    
    if [ ! -f "$CONFIG_FILE" ]; then
        return 1
    fi
    
    print_operation_start "加载配置文件" "$CONFIG_FILE"
    local start_time=$(date +%s)
    local current_group=""
    local repos=()
    
    while IFS= read -r line; do
        local parsed=$(parse_group_line "$line")
        if [ -n "$parsed" ]; then
            # 保存上一个分组的仓库列表
            if [ -n "$current_group" ] && [ ${#repos[@]} -gt 0 ]; then
                local IFS=$'\n'
                _CONFIG_GROUP_REPOS["$current_group"]="${repos[*]}"
                repos=()
            fi
            
            IFS='|' read -r group_name alias <<< "$parsed"
            current_group="$group_name"
            _CONFIG_GROUPS["$group_name"]="$alias"
        elif [ -n "$current_group" ] && [[ "$line" =~ ^-[[:space:]]+(.+)$ ]]; then
            local repo_name="${BASH_REMATCH[1]}"
            repo_name="${repo_name#"${repo_name%%[![:space:]]*}"}"
            repo_name="${repo_name%"${repo_name##*[![:space:]]}"}"
            [ -n "$repo_name" ] && repos+=("$repo_name")
        fi
    done < "$CONFIG_FILE"
    
    # 保存最后一个分组的仓库列表
    if [ -n "$current_group" ] && [ ${#repos[@]} -gt 0 ]; then
        local IFS=$'\n'
        _CONFIG_GROUP_REPOS["$current_group"]="${repos[*]}"
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local group_count=${#_CONFIG_GROUPS[@]}
    _CONFIG_LOADED=true
    print_operation_end "加载配置文件" "success" "$duration" "共 $group_count 个分组"
    return 0
}

# 解析分组行，提取分组名和代号
# 格式: ## 分组名 <!-- 代号 -->
parse_group_line() {
    local line=$1
    # 使用 bash 内置正则匹配，避免多次调用外部命令
    if [[ "$line" =~ ^##[[:space:]]+(.+)$ ]]; then
        local full_line="${BASH_REMATCH[1]}"
        local group_name="$full_line"
        local alias=""
        
        # 提取别名（如果存在），使用字符串操作提取
        if [[ "$full_line" == *"<!--"*"-->"* ]]; then
            # 提取 <!-- 和 --> 之间的内容
            local temp="${full_line#*<!--}"
            alias="${temp%%-->*}"
            # 去除别名中的空白
            alias="${alias#"${alias%%[![:space:]]*}"}"
            alias="${alias%"${alias##*[![:space:]]}"}"
            # 从分组名中移除别名部分
            group_name="${full_line%%<!--*}"
        fi
        
        # 去除首尾空白
        group_name="${group_name#"${group_name%%[![:space:]]*}"}"
        group_name="${group_name%"${group_name##*[![:space:]]}"}"
        
        echo "$group_name|$alias"
    fi
}

# 查找分组名（支持完整名称或代号）
find_group_name() {
    local input=$1
    local found_name=""
    
    # 加载配置缓存
    load_config_cache || {
        echo ""
        return 1
    }
    
    print_debug "查找分组: 输入='$input'"
    for group_name in "${!_CONFIG_GROUPS[@]}"; do
        local alias="${_CONFIG_GROUPS[$group_name]}"
        print_debug "  比较: 分组名='$group_name', 代号='$alias'"
        if [ "$group_name" = "$input" ] || [ "$alias" = "$input" ]; then
            found_name="$group_name"
            print_debug "  匹配成功: 找到分组 '$group_name'"
            break
        fi
        # 支持去掉"高地"后缀的匹配
        if [ -n "$alias" ]; then
            local alias_without="${alias%高地}"
            if [ "$alias_without" != "$alias" ] && [ "$alias_without" = "$input" ]; then
                found_name="$group_name"
                print_debug "  匹配成功（去掉'高地'后缀）: 找到分组 '$group_name'"
                break
            fi
        fi
    done
    
    if [ -z "$found_name" ]; then
        print_debug "  未找到匹配的分组"
    fi
    echo "$found_name"
}

# 获取分组文件夹名
get_group_folder() {
    local group_name=$1
    
    # 加载配置缓存
    load_config_cache || {
        echo "$group_name"
        return 1
    }
    
    # 从缓存中获取别名
    local group_alias="${_CONFIG_GROUPS[$group_name]}"
    
    # 如果有别名，使用别名（保留"高地"后缀）；否则使用分组名
    local folder="${group_alias:-$group_name}"
    echo "$folder"
}

# 获取指定分组的仓库列表
get_group_repos() {
    local group_name=$1
    
    # 加载配置缓存
    load_config_cache || {
        return 1
    }
    
    print_debug "获取分组 '$group_name' 的仓库列表"
    local repos_str="${_CONFIG_GROUP_REPOS[$group_name]}"
    
    if [ -n "$repos_str" ]; then
        echo "$repos_str"
        # 计算仓库数量（统计换行符数量）
        local repo_count=0
        while IFS= read -r; do
            [ -n "$REPLY" ] && ((repo_count++))
        done <<< "$repos_str"
        print_debug "分组 '$group_name' 共有 $repo_count 个仓库"
    else
        print_debug "分组 '$group_name' 没有仓库"
    fi
}

# 列出所有分组
list_groups() {
    print_step "正在读取配置文件: $CONFIG_FILE"
    
    # 加载配置缓存
    if ! load_config_cache; then
        print_error "分类文档不存在: $CONFIG_FILE"
        print_info "请参考 REPO-GROUPS.md.example 创建分类文档"
        print_info "或使用 PROMPT.md 中的 prompt 让 AI 生成"
        return
    fi
    
    print_info "可用分组："
    local group_count=0
    for group_name in "${!_CONFIG_GROUPS[@]}"; do
        local alias="${_CONFIG_GROUPS[$group_name]}"
        if [ -n "$alias" ]; then
            echo "  $group_name (代号: $alias)"
        else
            echo "  $group_name"
        fi
        ((group_count++))
    done
    print_info "共找到 $group_count 个分组"
}

# 获取所有分组名称（用于 -a 参数）
get_all_group_names() {
    # 加载配置缓存
    if ! load_config_cache; then
        return 1
    fi
    
    printf '%s\n' "${!_CONFIG_GROUPS[@]}"
}

