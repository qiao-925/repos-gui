# CloneX

> 一条命令同步你的所有 GitHub 仓库

CloneX 用一个 Gist 管理仓库分组，然后一条命令把本地仓库树同步出来：按组克隆、追加新仓库、生成 IDE workspace。

## 核心功能

- **Gist 驱动分组**：自动发现或创建 `REPO-GROUPS.md` Gist，作为仓库分组事实来源
- **自动追加未分类**：GitHub 上新增但未写入 Gist 的仓库自动进入 `未分类` 组
- **按组批量克隆**：按 Gist 分组创建本地目录，支持仓库级并行和单仓库 Git 并行连接
- **IDE workspace**：每个分组自动生成 `<group>.code-workspace`，方便 VS Code / Cursor / Windsurf 一键打开

## 前置条件

- **GitHub CLI**（`gh`）已安装并登录：`gh auth login`
- Python >= 3.10

## 安装

```bash
pip install clonex
```

## 使用

```bash
clonex
```

就这样。默认值已经够用：
- 输出目录：`./clonex-repos`
- 并行数：10 仓库 × 20 连接
- 认证：自动读取 `gh` 登录状态

> CloneX 不做自动分类。新仓库会进入 `未分类`，分组由你编辑 Gist 决定。

## GUI

> 待完善，暂未发布

## MCP Server

> 待完善，暂未发布

## 项目结构

```text
src/clonex/
├─ cli.py          # CLI 入口
├─ ui/             # GUI 入口与界面
├─ mcp/            # MCP Server 与工具注册
├─ application/    # 用例编排层
├─ core/           # 克隆、更新、workspace、并行执行
├─ domain/         # 分组解析、渲染与领域模型
└─ infra/          # GitHub API、Gist、认证、日志、路径
```

依赖方向：`ui / mcp → application → core / domain → infra`

## 依赖

- **Python**：`>=3.10`
- **GitHub / 存储**：`pygithub`、`requests`、`keyring`、`chardet`
- **GUI 可选**：`PyQt6`、`PyQt6-WebEngine`、`qt-material`
- **MCP 可选**：`mcp>=1.0`

## 文档

| 文档 | 用途 |
|------|------|
| `docs/ARCHITECTURE.md` | 架构全景与分层约束 |
| `docs/MCP-GUIDE.md` | MCP Server 使用与调试 |
| `docs/BUILD.md` | GUI 构建细节 |
| `docs/GIST-CONFIG-GUIDE.md` | Gist 云同步配置 |
