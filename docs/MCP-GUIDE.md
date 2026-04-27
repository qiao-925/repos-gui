# CloneX MCP Server 使用指南

把 CloneX 的能力以 Model Context Protocol (MCP) 暴露给 Claude Desktop、Cursor、Windsurf 等 agent 客户端。跟 GUI 不冲突，可以并存，共享同一份 keyring 凭证和本地配置。

## 前置条件

1. **先用 GUI 登录一次 GitHub**（MCP server 不会自己触发 OAuth，它直接读 keyring 里已有的 token）
2. **装好 [uv](https://docs.astral.sh/uv/)**

## 两种启动形态

### 形态 A：源码 + uv（MVP，当前可用）

用于开发者 / 已经克隆了仓库的用户。参考 `docs/mcp_config_dev.json`：

```json
{
  "mcpServers": {
    "clonex": {
      "command": "uv",
      "args": ["run", "--extra", "mcp", "python", "-m", "clonex.mcp"],
      "cwd": "<path-to-CloneX-repo>"
    }
  }
}
```

第一次运行会自动解析 `mcp` extras 并安装。

### 形态 B：PyPI + uvx（目标形态，Phase 2 可用）

发包到 PyPI 后，任何人零门槛使用。参考 `docs/mcp_config_uvx.json`：

```json
{
  "mcpServers": {
    "clonex": {
      "command": "uvx",
      "args": ["clonex-mcp"]
    }
  }
}
```

## 工具清单（14 个）

### A. 只读查询（4）

| 工具 | 用途 |
|---|---|
| `list_repos` | 拉取 GitHub owner 的仓库列表 |
| `read_groups` | 解析本地 `REPO-GROUPS.md` |
| `list_failed` | 读取上次运行的失败清单 |
| `get_auth_status` | 查看当前 GitHub 登录与 token 校验状态 |

### B. 分组写入（1）

| 工具 | 用途 |
|---|---|
| `write_groups` | 把 `{repo_name: group_name}` mapping 写回 `REPO-GROUPS.md`（默认 dry-run，实行增量合并） |

### C. 单仓库原子执行（3）

| 工具 | 用途 |
|---|---|
| `clone_repo` | 克隆一个仓库 |
| `pull_repo` | `git pull --ff-only` 单个本地仓库 |
| `check_repo` | `git fsck` 单个本地仓库（只读） |

### C2. 任意列表批量（3，带流式进度）

| 工具 | 用途 |
|---|---|
| `clone_repos_batch` | 任意列表并行克隆 |
| `pull_repos_batch` | 任意列表并行更新 |
| `check_repos_batch` | 任意列表并行校验 |

### D. 高层流程（3，带流式进度）

| 工具 | 用途 |
|---|---|
| `clone_group` | 按分组批量克隆 |
| `update_all` | 所有仓库批量 `git pull --ff-only` |
| `retry_failed` | 重试失败清单 |

## 安全护栏

- **所有写入/执行类工具默认 `dry_run=true`**——会返回"将要做什么"而不真的执行。agent 必须显式传 `dry_run: false` 才触发实际操作。`check_repo` / `check_repos_batch` 是只读校验，无需 dry-run。
- **凭证不经过 agent 对话**——token 在 MCP server 进程本地读 keyring，不出本机。
- **失败清单共享**——MCP `retry_failed` 读的是 GUI 写的同一份 `failed-repos.txt`，双向兼容。

## 并发说明

MCP server 和 GUI 是独立进程，**不要同时运行**。它们共享同一份 `REPO-GROUPS.md` 和 `failed-repos.txt`，并发写可能导致文件损坏。约定：一次只用一个入口。

## 统一错误结构

所有工具返回：

```json
// 成功
{"success": true, "data": {...}}

// 失败
{"success": false, "error": {"code": "E_xxx", "message": "...", "hint": "..."}}
```

错误码：`E_AUTH_MISSING` / `E_CONFIG_MISSING` / `E_GITHUB_API` / `E_GIT_EXEC` / `E_INVALID_ARG` / `E_INTERNAL`。

## 测试与调试

按从快到慢、从自动到手工的顺序，有三层：

### 1. 单元测试（pytest，全 mock，< 2 秒）

`tests/mcp/` 下有 ~50 个 case，通过 `mcp.shared.memory.create_connected_server_and_client_session` 把 `ClientSession` 和 FastMCP 实例用内存流连起来 — 没有子进程、没有 stdio、没有网络。所有外部副作用（GitHub API、keyring、文件系统）都被 monkeypatch 替换掉。这是 CI / 日常回归的核心：

```bash
uv run --group test pytest
```

改工具签名、调整返回结构、破坏 dry-run 默认值，这一层会立即告警。

### 2. End-to-end smoke（真凭证 + 真 API）

`scripts/mcp_smoke.py` 也走同一套内存 MCP 协议，但**不 mock 任何东西** — 用的是真 keyring token、真 GitHub API、真本地 `REPO-GROUPS.md`。用来快速确认"我改完以后在真实凭证下仍然能工作"：

```bash
uv run --group test python scripts/mcp_smoke.py
```

需要先用 CloneX GUI 登录过一次 GitHub。

### 3. MCP Inspector（官方 Web UI 手工调试）

任何一个 MCP 客户端上线前最后一关。它提供交互式界面，能看完整的 JSON-RPC 往返：

```bash
npx @modelcontextprotocol/inspector uv run --extra mcp python -m clonex.mcp
```

或（PyPI 发布后）：

```bash
npx @modelcontextprotocol/inspector uvx clonex-mcp
```

Inspector 会在浏览器打开一个 UI，列出 14 个工具，可以挨个填参数、观察响应、看协议日志。这是在 Claude Desktop / Cursor 里接入前**确认整条链路**的最佳工具。

## 参考

- `docs/mcp_config_dev.json` — 源码形态配置
- `docs/mcp_config_uvx.json` — PyPI 形态配置
- `docs/mcp_config_reference.json` — 第三方 MCP server 参考（GitHub MCP，非本项目）
