# Review 反馈（第 1 轮）

## 结论：不通过

## 高置信问题

### 问题 1：`AGENTS.md` MCP 工具清单与代码不一致
- `AGENTS.md:58` 写 `update_gist`，代码中是 `write_groups`（`src/gh_repos_sync/mcp/tools/groups.py:30`）
- `AGENTS.md:60` 写 `sync_to_gist`、`load_from_gist`，代码中不存在。实际流程组工具是 `clone_group`、`update_all`、`retry_failed`（`src/gh_repos_sync/mcp/tools/flows.py`）
- **修正**：`AGENTS.md:56-60` 应与 `docs/MCP-GUIDE.md:45-84` 和实际代码对齐

### 问题 2：`AGENTS.md` 引用不存在的文件
- `AGENTS.md:95` 写 `docs/AGENT-RULES-ARCHITECTURE.md`，该文件不存在
- **修正**：移除或替换为实际存在的文档

### 问题 3：`.windsurf/rules/clonex-release-gate.mdc` 被大幅删减
- 原文件 146 行被删减为约 89 行，移除了"核心定位"、"版本阶段规则"表格、"公共契约"章节
- 这些内容是经过多轮迭代建立的发布知识库
- **违背**：handoff 稳定区域要求"不废弃 `.windsurf` 规则文件"
- **修正**：恢复被删除的核心约束章节（可保留措辞优化，但不应丢失约束信息）

### 问题 4：`.gitignore` 中 `.windsurf/` 不应被忽略
- `.windsurf/` 被加入 `.gitignore` 会导致规则文件无法被 Git 跟踪
- **修正**：移除 `.gitignore` 中的 `.windsurf/`（用户已手动修复此条）
