#!/bin/bash
# 仓库克隆模块：实现单个仓库的克隆操作
#
# 主要功能：
#   - clone_repo()：克隆单个仓库，使用 Git 并行传输参数
#
# 特性：
#   - 直接克隆，不检查是否存在（覆盖）
#   - 失败时输出错误信息

# 克隆单个仓库
# 参数：
#   $1: repo_full (格式：owner/repo)
#   $2: repo_name (仓库名)
#   $3: group_folder (目标文件夹路径)
#   $4: parallel_connections (并行连接数，默认 8)
clone_repo() {
    # 禁用错误退出，让调用者处理错误
    set +e
    local repo_full="$1"
    local repo_name="$2"
    local group_folder="$3"
    local parallel_connections="${4:-8}"
    
    if [[ -z "$repo_full" || -z "$repo_name" || -z "$group_folder" ]]; then
        log_error "clone_repo: 参数不完整"
        set -e
        return 1
    fi
    
    # 构建目标路径
    local target_path="${group_folder}/${repo_name}"
    
    # 如果目录已存在，先删除（直接覆盖）
    if [[ -d "$target_path" ]]; then
        log_info "删除已存在的目录: $target_path"
        rm -rf "$target_path"
    fi
    
    # 确保目标文件夹的父目录存在
    mkdir -p "$group_folder"
    
    # 构建仓库 URL（使用 HTTPS）
    local repo_url="https://github.com/${repo_full}.git"
    
    # 执行克隆，使用 --jobs 参数实现并行传输，--progress 显示进度
    log_info "开始克隆: $repo_full -> $target_path"
    
    # 使用 --progress 显示 Git 的进度输出
    # Git 的进度信息默认输出到 stderr，不要重定向，让它直接输出（实时显示）
    # 不使用 2>&1，避免输出被缓冲
    if git clone --progress --jobs "$parallel_connections" "$repo_url" "$target_path"; then
        log_success "克隆成功: $repo_full"
        set -e
        return 0
    else
        log_error "克隆失败: $repo_full"
        # 如果克隆失败，清理不完整的目录
        if [[ -d "$target_path" ]]; then
            rm -rf "$target_path"
        fi
        set -e
        return 1
    fi
}

