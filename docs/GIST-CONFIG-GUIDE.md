# GitHub Gist 配置管理指南

## 概述

本应用支持通过 GitHub Gist 远程存储和管理 `REPO-GROUPS.md` 配置文件，实现多设备间的配置同步。

## 功能特性

- **远程存储**：将配置文件存储在 GitHub Gist 中
- **自动缓存**：本地缓存配置，支持离线使用
- **双向同步**：支持从 Gist 下载配置到本地，或上传本地配置到 Gist
- **版本管理**：Gist 自动保存历史版本，支持回滚
- **安全认证**：支持 GitHub Token 访问私有 Gist

## 使用方法

### 1. 创建 GitHub Token

1. 访问 [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
2. 点击 "Generate new token (classic)"
3. 选择权限：
   - `gist` (创建和管理 Gist)
   - `public_repo` (如果需要访问公开仓库信息)
4. 复制生成的 Token

### 2. 创建配置 Gist

#### 方法一：通过界面创建
1. 点击主界面的 "Gist 配置管理" 按钮
2. 输入 GitHub Token
3. 点击 "创建新 Gist"
4. 选择公开或私有
5. 系统会自动上传当前配置文件

#### 方法二：手动创建
1. 访问 [gist.github.com](https://gist.github.com)
2. 创建新的 Gist，文件名设为 `REPO-GROUPS.md`
3. 复制 Gist URL

### 3. 同步配置

#### 从 Gist 下载到本地
1. 在 "Gist 配置管理" 对话框中输入 Gist URL
2. 可选：输入 GitHub Token（私有 Gist 必需）
3. 点击 "从 Gist 下载"
4. 预览配置内容
5. 点击 "同步配置" 应用到本地

#### 上传本地配置到 Gist
1. 确保 Gist URL 已填写
2. 输入 GitHub Token（必需）
3. 点击 "上传到 Gist"

> 如果你更偏向自动化，可以通过 MCP 的 `write_groups` 工具维护分组；GUI 负责交互式查看和编辑，MCP 负责 Agent/脚本化写回。

### 4. 配置文件格式

Gist 中的配置文件格式与本地 `REPO-GROUPS.md` 完全相同：

```markdown
# GitHub 仓库分组

仓库所有者: your-username

## Personal
- repo-1
- repo-2

## Work
- work-project-1
- work-project-2
```

## 缓存机制

- **缓存位置**：`.gist_cache/gist_config.json`
- **缓存时间**：1 小时（自动刷新）
- **缓存内容**：已下载的配置文件内容和元数据
- **手动清理**：在 "Gist 配置管理" 中点击 "清理缓存"

## 最佳实践

### 1. 配置备份
- 上传配置前建议先备份本地文件
- 系统会在同步时自动创建 `.backup` 文件

### 2. Token 安全
- 妥善保管 GitHub Token
- 建议为 Gist 管理创建专门的 Token
- 定期轮换 Token

### 3. 团队协作
- 对于团队共享配置，建议创建公开 Gist
- 私有 Gist 适合个人配置

### 4. 版本管理
- Gist 自动保存历史版本
- 可在 GitHub 网站查看和恢复历史版本

## 故障排除

### 常见错误

#### "网络请求失败"
- 检查网络连接
- 确认 Gist URL 正确
- 检查防火墙设置

#### "Gist 中未找到文件"
- 确认 Gist URL 正确
- 检查文件名是否为 `REPO-GROUPS.md`
- 确认文件不为空

#### "上传配置需要 GitHub Token"
- 上传操作必须提供 Token
- 检查 Token 权限是否包含 `gist`

#### "配置格式错误"
- 检查配置文件格式
- 确认包含 "仓库所有者" 信息
- 验证分组语法正确

### 调试步骤

1. 检查日志文件 `logs/CloneX.log`
2. 验证 Gist URL 格式
3. 测试 GitHub Token 权限
4. 清理缓存重试

## URL 格式支持

支持以下 Gist URL 格式：

- `https://gist.github.com/username/gist_id`
- `https://gist.github.com/username/gist_id#file-REPO-GROUPS-md`
- 直接使用 Gist ID：`a1b2c3d4e5f6...`

## 高级用法

### 1. 多环境配置
可以为不同环境创建不同的 Gist：
- 开发环境：`dev-config-gist`
- 生产环境：`prod-config-gist`

### 2. 自动化方式
Gist 配置的自动化维护有两条路径：

- **GUI**：打开“Gist 配置管理”对话框，适合人工查看、编辑和同步。
- **MCP**：通过 `write_groups` 工具把分组映射写回 `REPO-GROUPS.md`，适合 Agent 或脚本化操作。

如果你想快速了解配置格式，请直接参考 `README.md` 的 Gist 格式示例。

## 相关文件

- `REPO-GROUPS.md`：本地配置文件
- `README.md`：Gist 分组格式示例
- `.gist_cache/`：缓存目录
- `logs/CloneX.log`：日志文件

## 技术实现

- **API 调用**：GitHub REST API v3
- **缓存格式**：JSON
- **认证方式**：Bearer Token
- **错误处理**：重试机制和用户友好错误提示
