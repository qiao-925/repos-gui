#!/bin/bash
# 配置解析模块：解析 REPO-GROUPS.md 配置文件
#
# 主要功能：
#   - parse_repo_groups()：解析配置文件，提取所有分组和仓库信息
#   - get_group_folder()：根据分组名和高地编号生成文件夹路径
#
# 配置文件格式：
#   ## 分组名 <!-- 高地编号 -->
#   - 仓库名1
#   - 仓库名2

readonly CONFIG_FILE="REPO-GROUPS.md"

# 获取项目目录（脚本所在目录）
# 如果 SCRIPT_DIR 已定义（从 main.sh 传入），使用它；否则动态计算
if [[ -z "${SCRIPT_DIR:-}" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
# repos 目录放在项目目录的上一级（同级目录）
# SCRIPT_DIR 已经是项目目录，所以上一级是 SCRIPT_DIR/..
readonly REPOS_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)/repos"

# 仓库所有者（从配置文件第一行提取）
REPO_OWNER=""

# 解析配置文件，提取分组和仓库信息
# 输出格式：每行一个任务，格式为 "repo_full|repo_name|group_folder|group_name"
parse_repo_groups() {
    local config_file="${1:-$CONFIG_FILE}"
    
    # 如果配置文件是相对路径，使用项目目录
    if [[ ! "$config_file" =~ ^/ ]] && [[ ! "$config_file" =~ ^[A-Za-z]: ]]; then
        config_file="${SCRIPT_DIR}/${config_file}"
    fi
    
    if [[ ! -f "$config_file" ]]; then
        log_error "配置文件不存在: $config_file"
        return 1
    fi
    
    # 提取仓库所有者（第一行：仓库所有者: xxx）
    REPO_OWNER=$(grep -E "^仓库所有者:" "$config_file" | head -1 | sed 's/仓库所有者:[[:space:]]*//')
    
    if [[ -z "$REPO_OWNER" ]]; then
        log_error "未找到仓库所有者信息"
        return 1
    fi
    
    local current_group=""
    local current_group_folder=""
    local current_highland=""
    
    # 定义正则表达式模式（避免在 [[ =~ ]] 中直接使用 < > 字符）
    local group_pattern='^##[[:space:]]+([^<]+)[[:space:]]*<!--[[:space:]]*([^>]+)[[:space:]]*-->'
    local repo_pattern='^-[[:space:]]+([^[:space:]]+)'
    
    while IFS= read -r line; do
        # 匹配分组标题：## 分组名 <!-- 高地编号 -->
        if [[ "$line" =~ $group_pattern ]]; then
            # 去除分组名两端空格
            current_group="${BASH_REMATCH[1]}"
            current_group="${current_group#"${current_group%%[![:space:]]*}"}"
            current_group="${current_group%"${current_group##*[![:space:]]}"}"
            # 去除高地编号两端空格
            current_highland="${BASH_REMATCH[2]}"
            current_highland="${current_highland#"${current_highland%%[![:space:]]*}"}"
            current_highland="${current_highland%"${current_highland##*[![:space:]]}"}"
            current_group_folder=$(get_group_folder "$current_group" "$current_highland")
        
        # 匹配仓库列表项：- 仓库名
        elif [[ "$line" =~ $repo_pattern ]]; then
            local repo_name="${BASH_REMATCH[1]}"
            local repo_full="${REPO_OWNER}/${repo_name}"
            
            if [[ -n "$current_group" && -n "$current_group_folder" ]]; then
                echo "${repo_full}|${repo_name}|${current_group_folder}|${current_group}"
            fi
        fi
    done < "$config_file"
}

# 根据分组名和高地编号生成文件夹路径
# 格式：组名 (高地编号)
get_group_folder() {
    local group_name="$1"
    local highland="$2"
    
    if [[ -n "$highland" ]]; then
        echo "${REPOS_DIR}/${group_name} (${highland})"
    else
        echo "${REPOS_DIR}/${group_name}"
    fi
}

