# CloneX

> GitHub 多仓库批量维护工具 —— **命令行 + 桌面 GUI + MCP Server 三入口**

CloneX 面向 GitHub 多仓库日常维护，提供批量克隆、批量更新、失败重试与 Gist 同步能力。工具依赖 GitHub 授权：首次使用先完成登录/授权，之后即可通过命令行一键执行。同一套业务核心同时面向**命令行**（一键默认执行）、**开发者**（PyQt6 GUI）与 **AI Agent**（MCP 协议）暴露，减少重复命令操作、提升多仓库维护效率。

## 核心功能

- **Gist 驱动的分组管理**：仓库分组配置存放在 GitHub Gist（`REPO-GROUPS.md`），CLI 自动发现/创建并维护这份配置。
- **按组并行克隆**：每个分组独立成一个本地子目录，符合"打开一组项目"的工作流。
- **自动生成 IDE workspace**：每个分组内自动生成 `<group>.code-workspace`，VS Code / Cursor / Windsurf 一键打开整个组。
- **自动追加未分类**：GitHub 上新增的仓库会自动追加到 gist 的"未分类"组，等用户手动归位。
- **CLI / GUI / MCP 三入口**：同一套业务核心，CLI 一键自动化，GUI 用于复杂交互，MCP 给 Agent 调用。

## Quick Start

### CLI

零参数即可运行——CLI 会自动发现/创建 gist、同步仓库列表、按组克隆、生成 workspace：

```bash
uv run clonex
```

执行流程：

1. 用缓存的 GitHub Token 解析 owner。
2. 发现你账号下的 `REPO-GROUPS.md` gist；若不存在则自动创建一个私有 gist（含初始模板）。
3. 把 GitHub 上新增的、gist 还没有的仓库追加到 `## 未分类` 组。
4. 解析 gist 内容，按组并行克隆到 `./clonex-repos/<组名>/<repo>/`。
5. 在每个组目录下生成 `<组名>.code-workspace`，引用该组所有 repo（相对路径）。
6. 最后打印 gist URL，方便你下次跑之前去 gist 里调整分组。

可选参数：

- `--owner`：GitHub owner。未传时优先使用已登录账号
- `--output`：克隆输出目录，默认 `./clonex-repos`
- `--tasks`：仓库级并行数，默认 `10`
- `--connections`：单仓库 Git 连接数，默认 `20`
- `--token`：手动覆盖 GitHub Token

> CLI 不提供"自动分类"——它只追加新仓库到"未分类"。具体分到哪个组，由你直接编辑 gist 决定。

### GUI

GUI 作为可选入口，保留复杂交互和可视化能力。

打包：

```bash
uv sync --group build
uv run pyinstaller --noconfirm --clean --onefile --windowed --name CloneX --paths src gui.py
```

启动：

- **Windows**：`./dist/BatchClone.exe`
- **Linux / macOS**：`chmod +x ./dist/BatchClone && ./dist/BatchClone`

### 安装发布

当前仓库已补充 PyPI 发布工作流。发布后用户可通过以下方式安装并使用命令行入口：

```bash
pip install clonex
clonex --help
```

如果你要先走测试发布，可以使用 TestPyPI 先验证：

```bash
pip install -i https://test.pypi.org/simple clonex
clonex --help
```

### MCP Server

MCP 作为可选入口，面向 Agent / 自动化场景。

开发模式（仓库源码直跑）：

```bash
uv run --extra mcp python -m gh_repos_sync.mcp
```

客户端接入示例（Claude Desktop / Cursor / Windsurf）见 `docs/mcp_config_dev.json` 与 `docs/mcp_config_uvx.json`，完整使用与调试指南见 `docs/MCP-GUIDE.md`。

### 测试

```bash
uv run --group test pytest                         # ~80 cases in-memory 单测（~3 秒）
uv run --group test python scripts/mcp_smoke.py    # 真 keyring 凭据 + 真 GitHub API smoke
```

交互式调试（MCP Inspector）：

```bash
npx @modelcontextprotocol/inspector uv run --extra mcp python -m gh_repos_sync.mcp
```

## 文档

| 文档 | 用途 |
|------|------|
| `AGENTS.md` | Agent 协作规则（分层约束、重打包规则） |
| `docs/MCP-GUIDE.md` | MCP Server 使用、测试与调试三层策略 |
| `docs/BUILD.md` | 打包细节 |
| `docs/GIST-CONFIG-GUIDE.md` | Gist 云同步配置 |

## 项目结构

```text
.
├─ gui.py                           # GUI 启动入口
├─ src/gh_repos_sync/cli.py         # 命令行启动入口（gist 驱动，按组克隆 + 生成 workspace）
├─ AGENTS.md                        # Agent 协作规则
├─ docs/                            # 文档、MCP 客户端配置示例
├─ scripts/
│  ├─ inspect_ui.py                 # AT-SPI UI 自检脚本
│  ├─ monitor_github.py             # GitHub Actions 监控
│  ├─ mcp_smoke.py                  # MCP 端到端 smoke 测试
│  ├─ rebuild-run.ps1               # 一键重打包并运行（Windows）
│  └─ watch-rebuild-run.ps1         # 监听文件变化后重打包运行
├─ tests/
│  ├─ mcp/                          # MCP 工具 in-memory 单测
│  ├─ test_workspace.py             # .code-workspace 生成单测
│  ├─ test_gist_discover.py         # gist 自动发现/创建单测
│  └─ test_sync_with_remote.py      # GitHub→gist 未分类同步单测
└─ src/
   └─ gh_repos_sync/
      ├─ ui/                        # 界面与交互层（GUI 入口）
      │  ├─ main_window.py          # 主窗口与主流程入口
      │  ├─ workers.py              # 后台任务线程
      │  ├─ auto_sync_dialog.py     # Gist 自动同步设置对话框
      │  ├─ gist_manager_dialog.py  # Gist 管理对话框
      │  ├─ theme.py                # 主题样式
      │  └─ chrome.py               # 窗口外观
      ├─ mcp/                       # MCP Server（Agent 入口）
      │  ├─ server.py               # 注册工具并启动 stdio
      │  ├─ app.py                  # FastMCP 单例
      │  ├─ context.py              # token / 路径共享助手
      │  ├─ errors.py               # 统一错误码与响应封装
      │  └─ tools/                  # A 查询 / B 分组写入 / C 单仓 / C2 批量 / D 流程
      ├─ application/               # 用例编排层
      │  ├─ local_generation.py     # 按语言规则分类流程
      │  ├─ sync_with_remote.py     # 把 GitHub 新增 repo 追加到 gist 未分类
      │  └─ execution.py            # 克隆/更新执行流程
      ├─ core/                      # 核心能力层
      │  ├─ repo_config.py          # 分组文件读写与 Gist 同步
      │  ├─ workspace.py            # 每组生成 .code-workspace
      │  ├─ clone.py                # 单仓库克隆
      │  ├─ pull.py                 # 单仓库更新
      │  ├─ parallel.py             # 并行任务调度
      │  ├─ check.py                # 仓库完整性校验
      │  ├─ failed_repos.py         # 失败仓库记录
      │  └─ process_control.py      # 执行过程控制
      ├─ domain/                    # 领域规则层
      │  ├─ models.py               # 领域模型
      │  └─ repo_groups.py          # 分组解析与渲染
      └─ infra/                     # 基础设施层
         ├─ auth.py                 # GitHub OAuth 授权
         ├─ github_api.py           # GitHub API 封装
         ├─ gist_config.py          # Gist 配置管理（含自动发现/创建）
         ├─ auto_gist_sync.py       # 自动 Gist 同步
         ├─ logger.py               # 日志
         └─ paths.py                # 运行路径
```

依赖方向：`ui / mcp → application → core / domain → infra`

## 可读性优化计划

以下计划优先围绕“让新成员更快读懂项目、让维护者更快定位逻辑”展开，按低风险到高收益排序执行。

### 第一阶段：快速提升结构可读性

1. **补一份项目总览**
   - 明确这套工具解决什么问题、三入口分别适合什么场景。
   - 用一段话说明 CLI / GUI / MCP 的关系，减少读者在入口之间来回切换。

2. **统一目录职责描述**
   - 保证 `ui`、`mcp`、`application`、`core`、`domain`、`infra` 的边界一致。
   - 把“功能说明”写成“职责说明”，避免目录注释和实际代码职责不一致。

3. **收敛入口说明**
   - 保留一个“推荐使用方式”，其余入口作为可选方案。
   - 避免读者第一次进入 README 时同时看到过多启动路径。

### 第二阶段：降低代码阅读成本

4. **整理命名一致性**
   - 统一仓库、分组、同步、任务、流程等核心名词。
   - 避免同一概念在 CLI、GUI、MCP 中出现不同叫法。

5. **拆解高复杂度模块**
   - 优先检查主窗口、批量执行、Gist 同步、失败重试等逻辑。
   - 把“流程编排”和“具体执行”分离，减少单文件横跨过多职责。

6. **补充关键注释与设计说明**
   - 重点解释为什么要这样设计，而不是重复代码做了什么。
   - 在复杂分支、特殊兼容逻辑、失败兜底处补足上下文。

### 第三阶段：建立长期约束

7. **固化规范**
   - 增加命名、目录、错误处理、注释风格的约定。
   - 让后续新代码直接按统一规范进入，减少回潮。

8. **把可读性纳入检查流程**
   - 在 review 或自检时增加“是否职责单一、命名清晰、入口明确”的检查项。
   - 对新增文件和大改动优先要求附带说明。

### 执行原则

- 先改“读者第一眼会困惑”的地方，再改细节。
- 先统一结构和入口，再统一命名和实现。
- 以小步迭代为主，避免一次性大重构影响稳定性。
- 每次修改后都回看 README 与目录是否仍然自洽。

### 建议验收标准

- 新人能在 5 分钟内说清项目入口和分层。
- 每个目录都能用一句话准确描述职责。
- 核心流程无需依赖口头解释即可定位到对应文件。
- 复杂逻辑有足够上下文，读代码时不需要反复猜测。

## 依赖

- **Python** `>=3.10`
- **GUI**：`PyQt6`、`PyQt6-WebEngine`、`qt-material`
- **GitHub / 存储**：`pygithub`、`requests`、`keyring`、`chardet`
- **MCP**（可选，`uv sync --extra mcp`）：`mcp>=1.0`
- **打包**（`uv sync --group build`）：`pyinstaller`
- **测试**（`uv sync --group test`）：`pytest`、`anyio`、`mcp`