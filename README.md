# CloneX

> GitHub 多仓库批量维护工具 —— **命令行 + 桌面 GUI + MCP Server 三入口**

CloneX 面向 GitHub 多仓库日常维护，提供批量克隆、批量更新、失败重试与 Gist 同步能力。工具依赖 GitHub 授权：首次使用先完成登录/授权，之后即可通过命令行一键执行。同一套业务核心同时面向**命令行**（一键默认执行）、**开发者**（PyQt6 GUI）与 **AI Agent**（MCP 协议）暴露，减少重复命令操作、提升多仓库维护效率。

## 核心功能

- **批量克隆与更新**：同步 GitHub 仓库列表，按需克隆或更新本地仓库。
- **分组与失败闭环**：支持仓库分组管理，自动记录失败任务清单并支持重试。
- **CLI 优先**：默认以命令行方式执行，适合直接安装和分发。
- **GUI / MCP 可选**：GUI 用于复杂交互，MCP 作为独立入口用于 Agent 自动化。

## Quick Start

### CLI

默认直接执行一键并行拉取并克隆所有仓库：

```bash
uv run clonex
```

可选参数：

- `--owner`：GitHub owner。未传时优先使用已登录账号
- `--output`：克隆输出目录，默认 `./clonex-repos`
- `--tasks`：仓库级并行数，默认 `10`
- `--connections`：单仓库 Git 连接数，默认 `20`
- `--token`：手动覆盖 GitHub Token

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
uv run --group test pytest                         # ~50 cases in-memory 单测（~1 秒）
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
├─ src/gh_repos_sync/cli.py         # 命令行启动入口（拉取 list 并直接克隆）
├─ AGENTS.md                        # Agent 协作规则
├─ docs/                            # 文档、MCP 客户端配置示例
├─ scripts/
│  ├─ inspect_ui.py                 # AT-SPI UI 自检脚本
│  ├─ monitor_github.py             # GitHub Actions 监控
│  ├─ mcp_smoke.py                  # MCP 端到端 smoke 测试
│  ├─ rebuild-run.ps1               # 一键重打包并运行（Windows）
│  └─ watch-rebuild-run.ps1         # 监听文件变化后重打包运行
├─ tests/
│  └─ mcp/                          # MCP 工具 in-memory 单测（~50 cases）
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
      │  └─ execution.py            # 克隆/更新执行流程
      ├─ core/                      # 核心能力层
      │  ├─ repo_config.py          # 分组文件读写与 Gist 同步
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
         ├─ gist_config.py          # Gist 配置管理
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