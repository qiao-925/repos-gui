# CloneX

> GitHub 多仓库批量维护工具 —— **CLI + GUI + MCP Server**

CloneX 面向需要长期维护很多 GitHub 仓库的开发者。它用一个 `REPO-GROUPS.md` Gist 管理仓库分组，然后一条命令把本地仓库树同步出来：按组克隆、追加未分类仓库，并为每个分组生成 IDE workspace。

## 核心功能

- **Gist 驱动分组**：自动发现或创建 `REPO-GROUPS.md` Gist，并把它作为仓库分组事实来源。
- **自动追加未分类**：GitHub 上新增但未写入 Gist 的仓库会自动进入 `未分类` 组。
- **按组批量克隆**：按 Gist 分组创建本地目录，支持仓库级并行和单仓库 Git 并行连接。
- **安全路径处理**：分组名会转换为安全目录名，例如 `AI / Agents` 会落盘为 `AI _ Agents`。
- **IDE workspace**：每个分组自动生成 `<group>.code-workspace`，方便 VS Code / Cursor / Windsurf 一键打开。
- **三入口复用核心能力**：CLI 面向自动化，GUI 面向人工操作，MCP Server 面向 Agent 调用。

## 安装

推荐从 PyPI 安装 CLI：

```bash
pip install clonex
clonex --help
```

按需安装可选入口：

```bash
pip install "clonex[gui]"   # 提供 clonex-gui
pip install "clonex[mcp]"   # 提供 clonex-mcp
```

源码开发：

```bash
uv sync
uv run clonex --help
```

## 快速开始

### CLI 一键同步

```bash
clonex
```

首次运行需要 GitHub 授权。可以先通过 GUI 完成登录，也可以显式传入 token：

```bash
clonex --token <github-token>
```

常用参数：

```bash
clonex --output ./clonex-repos --tasks 10 --connections 20
```

- `--owner`：GitHub owner。未传时优先使用已登录账号。
- `--output`：克隆输出目录，默认 `./clonex-repos`。
- `--tasks`：仓库级并行数，默认 `10`。
- `--connections`：单仓库 Git 连接数，默认 `20`。
- `--token`：手动覆盖 GitHub Token。

执行流程：

1. 读取 GitHub Token 并解析 owner。
2. 自动发现或创建 `REPO-GROUPS.md` Gist。
3. 将 GitHub 新增仓库追加到 `## 未分类`。
4. 解析 Gist，按组克隆到 `./clonex-repos/<safe-group>/<repo>/`。
5. 为每个组生成 `<group>.code-workspace`。
6. 打印 Gist URL，方便继续手动调整分组。

> CloneX 不做自动分类。它只负责把新增仓库追加到 `未分类`，具体分组由你编辑 Gist 决定。

### Gist 分组格式

CloneX 使用 `REPO-GROUPS.md` 作为分组事实来源。最小格式：

```md
# GitHub 仓库分组

仓库所有者: qiao-925

## Personal
- typing-hub
- mobile-typing

## AI / Agents
- news-digest
```

上面的 `AI / Agents` 会落盘为 `AI _ Agents`，避免 `/` 被系统解释为路径分隔符。

## GUI

安装并启动：

```bash
pip install "clonex[gui]"
clonex-gui
```

本地打包：

```bash
uv sync --group build
uv run pyinstaller --noconfirm --clean --onefile --windowed --name CloneX --paths src gui.py
```

打包产物：

- **Windows**：`./dist/CloneX.exe`
- **Linux / macOS**：`chmod +x ./dist/CloneX && ./dist/CloneX`

## MCP Server

MCP Server 面向 Agent / 自动化场景。

安装并启动：

```bash
pip install "clonex[mcp]"
clonex-mcp
```

源码开发模式：

```bash
uv run --extra mcp python -m gh_repos_sync.mcp
```

客户端接入示例见 `docs/mcp_config_dev.json` 与 `docs/mcp_config_uvx.json`。完整说明见 `docs/MCP-GUIDE.md`。

## 开发与验证

```bash
uv sync --group test
uv run --group test pytest -q
uv build
```

可选 smoke：

```bash
uv run --group test python scripts/mcp_smoke.py
```

交互式调试 MCP：

```bash
npx @modelcontextprotocol/inspector uv run --extra mcp python -m gh_repos_sync.mcp
```

## 发布到 PyPI

当前包名：`clonex`。当前版本仍处于 `0.x` 阶段，表示功能可用但 API 与发布节奏尚未承诺稳定。

发布前本地检查：

```bash
uv run --group test pytest -q
uv build
```

推荐流程：

1. 先完成测试、构建、README 核对和真实低并发 smoke。
2. 更新 `pyproject.toml` 的版本号，例如 `0.1.0`。
3. 提交并推送版本修改。
4. 确认 GitHub Actions secret `PYPI_API_TOKEN` 已配置为正式 PyPI token。
5. 手动运行 GitHub Actions 的 `Publish Package` workflow。
6. 发布后用隔离环境验证：

```bash
pip install clonex==0.1.0
clonex --help
```

当前不使用 TestPyPI，也不通过 tag 或 GitHub Release 自动触发发布，避免草率发布。

## 项目结构

```text
.
├─ gui.py                           # GUI 启动入口
├─ src/gh_repos_sync/cli.py         # CLI 启动入口
├─ docs/                            # 文档、MCP 客户端配置示例
├─ scripts/                         # smoke、打包和辅助脚本
├─ tests/                           # 单元测试与 MCP 测试
└─ src/gh_repos_sync/
   ├─ ui/                           # GUI 入口与界面
   ├─ mcp/                          # MCP Server 与工具注册
   ├─ application/                  # 用例编排层
   ├─ core/                         # 克隆、更新、workspace、并行执行
   ├─ domain/                       # 分组解析、渲染与领域模型
   └─ infra/                        # GitHub API、Gist、认证、日志、路径
```

依赖方向：`ui / mcp → application → core / domain → infra`

## 依赖

- **Python**：`>=3.10`
- **GitHub / 存储**：`pygithub`、`requests`、`keyring`、`chardet`
- **GUI 可选依赖**：`PyQt6`、`PyQt6-WebEngine`、`qt-material`
- **MCP 可选依赖**：`mcp>=1.0`
- **构建工具**：`setuptools`、`wheel`、`uv`

## 文档

| 文档 | 用途 |
|------|------|
| `docs/MCP-GUIDE.md` | MCP Server 使用、测试与调试 |
| `docs/BUILD.md` | 打包细节 |
| `docs/GIST-CONFIG-GUIDE.md` | Gist 云同步配置 |
