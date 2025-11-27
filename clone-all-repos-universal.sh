#!/bin/bash
# GitHub 仓库同步脚本（跨平台版本）
# 功能：保持本地仓库与 GitHub 远程仓库完全同步（增删改查）
# 使用方法: 
#   Windows (Git Bash/PowerShell): bash clone-all-repos-universal.sh
#   Linux/macOS: bash clone-all-repos-universal.sh 或 ./clone-all-repos-universal.sh

echo "正在获取您的所有 GitHub 仓库列表..."

# 自动添加 GitHub 主机密钥到 known_hosts（避免首次连接时的交互提示）
if [ ! -f ~/.ssh/known_hosts ] || ! grep -q "github.com" ~/.ssh/known_hosts 2>/dev/null; then
    echo "正在添加 GitHub 主机密钥..."
    mkdir -p ~/.ssh
    ssh-keyscan -t rsa,ecdsa,ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null || true
fi

# 获取所有仓库（包括私有仓库）
repos=$(gh repo list --limit 1000 --json nameWithOwner --jq '.[].nameWithOwner')

if [ $? -ne 0 ]; then
    echo "错误: 无法获取仓库列表。请确保已登录 GitHub CLI (运行: gh auth login)"
    exit 1
fi

# 转换为数组
repo_array=($repos)
total_repos=${#repo_array[@]}

if [ $total_repos -eq 0 ]; then
    echo "未找到任何仓库。"
    exit 0
fi

echo "找到 $total_repos 个远程仓库，开始同步..."
echo ""

success_count=0
update_count=0
fail_count=0

for repo in $repos; do
    repo=$(echo $repo | tr -d '\r\n')
    
    # 提取仓库名称（用于本地文件夹名）
    repo_name=$(basename $repo)
    
    # 检查是否已存在
    if [ -d "$repo_name" ]; then
        # 检查是否是 git 仓库
        if [ -d "$repo_name/.git" ]; then
            echo -n "[更新] $repo... "
            cd "$repo_name"
            
            # 检查是否在分支上，如果不在则切换到默认分支
            current_branch=$(git symbolic-ref -q HEAD 2>/dev/null)
            if [ -z "$current_branch" ]; then
                # 不在分支上，尝试切换到默认分支（通常是 main 或 master）
                default_branch=$(git remote show origin 2>/dev/null | grep "HEAD branch" | sed 's/.*: //' || echo "main")
                git checkout -b "$default_branch" 2>/dev/null || git checkout "$default_branch" 2>/dev/null || true
            fi
            
            # 获取当前分支名并拉取
            branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
            git pull origin "$branch" --quiet 2>/dev/null || git pull --quiet
            
            if [ $? -eq 0 ]; then
                echo "✓ 成功"
                ((update_count++))
            else
                echo "✗ 失败"
                ((fail_count++))
            fi
            cd ..
        else
            echo "[跳过] $repo - 目录已存在但不是 git 仓库"
            ((fail_count++))
        fi
        continue
    fi
    
    echo -n "[克隆] $repo... "
    
    # 克隆仓库
    gh repo clone "$repo"
    
    if [ $? -eq 0 ]; then
        echo "✓ 成功"
        ((success_count++))
    else
        echo "✗ 失败"
        ((fail_count++))
    fi
done

echo ""
echo "=================================================="
echo "同步操作完成（增/改）"
echo "新增: $success_count"
echo "更新: $update_count"
echo "失败: $fail_count"
echo "=================================================="
echo ""

# 检查并删除远程已删除的本地仓库（删）
echo "正在检查需要删除的本地仓库（远程已不存在）..."
delete_count=0

# 获取远程仓库名称列表（用于比较）
remote_repo_names=()
for repo in $repos; do
    repo=$(echo $repo | tr -d '\r\n')
    repo_name=$(basename $repo)
    remote_repo_names+=("$repo_name")
done

# 遍历当前目录下的所有目录
for local_dir in */; do
    # 移除末尾的斜杠
    local_dir=${local_dir%/}
    
    # 跳过非目录
    if [ ! -d "$local_dir" ]; then
        continue
    fi
    
    # 只检查 git 仓库
    if [ ! -d "$local_dir/.git" ]; then
        continue
    fi
    
    # 检查是否在远程仓库列表中
    found=false
    for remote_name in "${remote_repo_names[@]}"; do
        if [ "$local_dir" == "$remote_name" ]; then
            found=true
            break
        fi
    done
    
    # 如果本地存在但远程不存在，则删除
    if [ "$found" == false ]; then
        echo -n "[删除] $local_dir (远程仓库已不存在)... "
        rm -rf "$local_dir"
        if [ $? -eq 0 ]; then
            echo "✓ 已删除"
            ((delete_count++))
        else
            echo "✗ 删除失败"
        fi
    fi
done

if [ $delete_count -eq 0 ]; then
    echo "没有需要删除的本地仓库。"
else
    echo ""
    echo "已删除 $delete_count 个本地仓库（远程已不存在）。"
fi

echo ""
echo "=================================================="
echo "✅ 同步完成！本地与远程已完全一致"
echo "新增: $success_count"
echo "更新: $update_count"
echo "删除: $delete_count"
echo "失败: $fail_count"
echo "=================================================="

