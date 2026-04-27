# `scripts/` 说明

本目录保留仓库级辅助脚本，不承担核心业务逻辑。这里不迁移、不删除任何脚本，只负责明确归属和用途。

## 正式辅助脚本

这些脚本与用户工作流、GUI 或 MCP 验证直接相关，属于正式辅助资产：

- `mcp_smoke.py`：MCP 真实凭证 smoke test，README 中引用的验证脚本。
- `inspect_ui.py`：GUI 可访问性 / 界面检查脚本，供 `build.yml` 的 smoke-test 使用。
- `handoff_state.py`：整理当前工作状态，方便跨会话或交接。
- `relay_to_cursor.py`：把信息转发到 Cursor 相关工作流。

## 开发辅助脚本

这些脚本主要服务本地开发、调试或循环运行，不属于正式对外工作流：

- `generate_task_log.py`：生成任务日志。
- `monitor_github.py`：监控 GitHub 相关状态或事件。
- `rebuild-run.ps1`：重新构建并运行 GUI 的 Windows 辅助脚本。
- `watch-rebuild-run.ps1`：监听变更后自动重建并运行的 Windows 辅助脚本。

## 归属原则

- 正式辅助脚本可以被 `README.md`、`docs/` 或 workflow 引用。
- 开发辅助脚本保留在仓库内，主要供维护者本地使用。
- 未来如果脚本演化为稳定入口，再考虑提升为文档引用或入口命令。
