# Review Workflow

## Goal

Review Cursor-delivered changes against current handoff constraints

## Steps

1. 读取 `handoff/current-task.md`
2. 若存在 `handoff/state.json`，先读取它，并优先使用其中的 `target_files`、`changed_files` 与 `status`
3. 读取当前仓库实际代码 diff，确认 Cursor 改了哪些文件
4. 只聚焦当前 handoff 任务做 review，不发散到无关文件
5. 优先对比这些内容：
   - 是否符合 `handoff/current-task.md` 中的目标、范围与约定边界
   - 是否满足 `Do NOT` 边界
   - 是否保持主链路、数据结构、输出语言不变
   - 是否完成要求的自检，或至少提供了可信的自检结果
6. 若发现问题，只报告高置信问题：
   - 先说明问题是什么
   - 再说明为何会错或违背什么
   - 最后给出最小修正建议
7. 若没有发现高置信问题，明确给出"通过"，并说明可以继续下一步
8. review 完成后，若存在 `handoff/state.json`，将其状态更新为 `reviewed`
9. review 结束时，输出结论必须是以下两种之一：
   - `通过：可继续下一步`
   - `不通过：先修复上述问题`
