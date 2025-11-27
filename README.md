# GitHub 仓库同步脚本

使用 GitHub CLI 保持本地仓库与 GitHub 远程仓库完全同步的脚本。

## 🎯 核心功能

这是一个**完整的同步工具**，不仅仅是克隆，而是实现本地与远程的**完全一致**：

- ✅ **增**：自动克隆远程存在但本地不存在的仓库
- ✅ **改**：自动更新本地已存在的仓库（`git pull`）
- ✅ **删**：自动删除本地存在但远程已删除的仓库
- ✅ **查**：显示同步进度和统计信息

**目标**：无论远程仓库是增加、修改还是删除，本地都会自动同步保持一致。

## 前置要求

1. 安装 [GitHub CLI](https://cli.github.com/)
2. 登录 GitHub CLI：
   ```bash
   gh auth login
   ```

## 使用方法

**所有系统通用（Windows/Linux/macOS）：**

```bash
bash clone-all-repos-universal.sh
```

或者在 Linux/macOS/Git Bash 上：

```bash
chmod +x clone-all-repos-universal.sh
./clone-all-repos-universal.sh
```

> **提示**：
> - Windows 用户需要安装 [Git Bash](https://git-scm.com/downloads) 或使用 WSL
> - 脚本会在当前目录下同步所有仓库

## 同步机制详解

脚本会执行完整的同步操作，确保本地与远程**完全一致**：

### 1. 增（新增仓库）
- 检测远程存在但本地不存在的仓库
- 自动克隆到本地

### 2. 改（更新仓库）
- 检测本地已存在的仓库
- 自动执行 `git pull` 更新到最新版本

### 3. 删（删除仓库）
- 检测本地存在但远程已删除的仓库
- 自动删除本地目录

### 4. 查（统计信息）
- 显示新增、更新、删除的数量
- 显示失败的操作

⚠️ **重要提示**：
- 删除操作会**永久删除**本地目录，请确保您确实想要删除这些仓库
- 脚本只处理 Git 仓库（包含 `.git` 目录的文件夹）
- 非 Git 仓库目录不会被删除

## 注意事项

- 脚本会在**当前目录**下同步所有仓库
- 确保有足够的**磁盘空间**和**网络连接**
- 删除操作**不可逆**，请谨慎使用
- 建议在运行前先备份重要数据
- Windows 用户需要安装 Git Bash 或使用 WSL 来运行 Bash 脚本

## 自定义选项

如果需要克隆特定组织的仓库，可以修改脚本中的 `gh repo list` 命令：

```bash
# 克隆特定组织的所有仓库
gh repo list <组织名> --limit 1000 --json nameWithOwner --jq '.[].nameWithOwner'
```

