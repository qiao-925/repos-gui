#!/bin/bash
# GitHub 仓库操作函数

# 缓存 GitHub 用户名（避免重复调用 API）
_GITHUB_USER_CACHE=""

# 获取 GitHub 用户名（带缓存）
get_github_username() {
    if [ -z "$_GITHUB_USER_CACHE" ]; then
        print_api_call "gh api user" "--jq '.login'"
        print_operation_start "获取 GitHub 用户名" ""
        local start_time=$(date +%s)
        _GITHUB_USER_CACHE=$(gh api user --jq '.login' 2>/dev/null || echo "")
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        if [ -n "$_GITHUB_USER_CACHE" ]; then
            print_operation_end "获取 GitHub 用户名" "success" "$duration" "用户: $_GITHUB_USER_CACHE"
        else
            print_operation_end "获取 GitHub 用户名" "fail" "$duration" ""
        fi
    else
        print_info "使用缓存的 GitHub 用户名: $_GITHUB_USER_CACHE"
    fi
    echo "$_GITHUB_USER_CACHE"
}

# 初始化 GitHub 连接（添加 SSH 密钥）
init_github_connection() {
    print_step "检查 SSH 配置..."
    print_operation_start "检查 SSH known_hosts" ""
    if [ ! -f ~/.ssh/known_hosts ] || ! grep -q "github.com" ~/.ssh/known_hosts 2>/dev/null; then
        print_info "正在添加 GitHub 主机密钥..."
        print_command "ssh-keyscan -t rsa,ecdsa,ed25519 github.com"
        local start_time=$(date +%s)
        mkdir -p ~/.ssh
        ssh-keyscan -t rsa,ecdsa,ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null || true
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        print_operation_end "添加 GitHub 主机密钥" "success" "$duration" ""
    else
        print_info "GitHub 主机密钥已存在，跳过添加"
    fi
    
    # 配置 Git 加速选项（直接设置，git config 本身很快，检查反而更慢）
    print_step "配置 Git 加速选项..."
    print_operation_start "配置 Git 全局选项" ""
    local start_time=$(date +%s)
    print_command "git config --global http.postBuffer 524288000"
    git config --global http.postBuffer 524288000 2>/dev/null || true  # 500MB 缓冲区
    print_command "git config --global http.lowSpeedLimit 0"
    git config --global http.lowSpeedLimit 0 2>/dev/null || true
    print_command "git config --global http.lowSpeedTime 0"
    git config --global http.lowSpeedTime 0 2>/dev/null || true
    print_command "git config --global core.preloadindex true"
    git config --global core.preloadindex true 2>/dev/null || true
    print_command "git config --global core.fscache true"
    git config --global core.fscache true 2>/dev/null || true
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    print_operation_end "配置 Git 全局选项" "success" "$duration" "HTTP 缓冲区: 500MB"
    print_info "使用官方 GitHub (github.com)"
}

# 获取所有远程仓库列表
fetch_remote_repos() {
    print_step "通过 GitHub CLI 获取仓库列表..."
    local all_repos=$(gh repo list --limit 1000 --json nameWithOwner --jq '.[].nameWithOwner')
    
    if [ $? -ne 0 ]; then
        print_error "无法获取仓库列表。请确保已登录 GitHub CLI (运行: gh auth login)"
        exit 1
    fi
    
    local repo_count=$(echo "$all_repos" | wc -l | tr -d ' ')
    print_success "成功获取 $repo_count 个远程仓库"
    print_debug "远程仓库列表: $(echo "$all_repos" | head -5 | tr '\n' ', ')..."
    
    echo "$all_repos"
}

# 查找仓库的完整名称（owner/repo）
find_repo_full_name() {
    local repo_name=$1
    local repo_owner=$(get_github_username)
    
    if [ -z "$repo_owner" ]; then
        print_error "无法获取仓库所有者，跳过仓库: $repo_name"
        return 1
    fi
    
    # 尝试检查仓库是否存在
    local repo_full="$repo_owner/$repo_name"
    print_api_call "gh repo view" "$repo_full"
    print_operation_start "检查仓库是否存在" "$repo_full"
    local start_time=$(date +%s)
    if gh repo view "$repo_full" &>/dev/null; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        print_operation_end "检查仓库是否存在" "success" "$duration" "$repo_full"
        echo "$repo_full"
        return 0
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        print_operation_end "检查仓库是否存在" "fail" "$duration" "$repo_full (仓库不存在)"
        return 1
    fi
}

