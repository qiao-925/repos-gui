# GitHub 仓库管理器

集中管理所有 GitHub 仓库的工具仓库。

## 🎯 功能

- 📋 **分组管理**: 按主题对仓库进行分类
- 🚀 **按需同步**: 只同步需要的分组，节省时间和空间
- 🔍 **Workspace 支持**: 为每个分组创建 VS Code/Cursor workspace
- 📖 **文档索引**: 清晰的分类文档，快速查找仓库

## 📚 仓库分组

查看 [REPO-GROUPS.md](./REPO-GROUPS.md) 了解所有分组。

## 🚀 使用方法

### 同步特定分组

```bash
# 同步 Go 学习相关仓库
bash scripts/sync-group.sh go-learning

# 同步 Java 学习相关仓库
bash scripts/sync-group.sh java-learning

# 同步书籍学习相关仓库
bash scripts/sync-group.sh book-learning
```

### 打开 Workspace

1. 在 VS Code/Cursor 中打开对应的 `.code-workspace` 文件
2. 例如：打开 `workspaces/go-learning.code-workspace` 查看所有 Go 学习仓库

## 📁 目录结构

```
github-repos-manager/
├── README.md                    # 本文件
├── REPO-GROUPS.md              # 仓库分组索引文档
├── repo-groups.json            # 仓库分组配置文件（JSON格式）
├── workspaces/                  # VS Code workspace 配置文件
│   ├── go-learning.code-workspace
│   ├── java-learning.code-workspace
│   └── ...
├── scripts/                     # 同步脚本
│   ├── sync-group.sh           # 按分组同步脚本
│   └── sync-all.sh             # 全局同步脚本（可选）
└── .gitignore                   # Git 忽略配置
```

## 🔧 前置要求

1. 安装 [GitHub CLI](https://cli.github.com/)
2. 登录 GitHub CLI：
   ```bash
   gh auth login
   ```

## 📝 注意事项

- 仓库会克隆到当前目录的**同级目录**（`../`）
- 确保有足够的**磁盘空间**和**网络连接**
- 删除操作**不可逆**，请谨慎使用

## 🔗 相关链接

- 远程仓库: https://github.com/qiao-925/github-repos-manager
