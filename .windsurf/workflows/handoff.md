---
auto_execution_mode: 0
description: 调研当前任务并生成 Cursor-executable prompt
---
# Handoff Workflow

## Goal

调研当前任务并生成 Cursor-executable prompt

## Steps

1. 读取当前任务描述（用户输入或当前对话上下文）
2. 调研相关代码：
   - 找到所有涉及的文件路径和行号
   - 理清依赖关系和调用链
   - 识别不应修改的稳定代码
3. 读取模板：`prompts/cursor-task-template.md`
4. 先将交接内容转为文件，再基于文件填充模板；跨工具协作优先通过文件中转，不依赖对话上下文总结
5. 将本步结果写入 `handoff/current-task.md` 和 `handoff/cursor-prompt.md`
6. 填充模板，输出完整的 Cursor prompt，要求：
   - `Context` 中每个文件必须带精确行号
   - `What to change` 每一步必须独立执行，不依赖 AI 主动推断
   - `Do NOT` 列出所有不应动的文件或范围
7. 若当前环境支持 relay，则在生成 `handoff/cursor-prompt.md` 后默认进入 relay 流程：
   - 先检查 Cursor 窗口是否可定位（`--action check`）
   - 默认使用 `paste-and-send` + `--send-key return`，即粘贴后模拟按 Enter 键触发 Cursor 执行（相当于点击发送按钮）
   - 仅当用户明确要求只粘贴不发送时，才回退到 `paste`
8. relay 完成后，调用状态脚本写入 `handoff/state.json`，记录：
   - 当前状态为 `awaiting_cursor`
   - 当前 handoff 关注的目标文件
   - 这些目标文件在发送前的基线快照
9. relay 只负责粘合和触发，不负责思考型传递、全域总结或跨工具重建上下文；若当前环境不支持 relay，则回退为手动复制 `handoff/cursor-prompt.md`
10. relay 完成后，启动 watcher 等待 Cursor 完成：
    - 执行 `python scripts/watch_handoff.py --block --timeout 600`
    - watcher 会持续检测 `handoff/state.json` 和目标文件变化
    - 检测机制（三层）：
      - Cursor 按 prompt 协议主动执行 `handoff_state.py detect` 写回 `review_ready`（最可靠）
      - 目标文件变更后静默 90 秒无新变化，自动执行 detect（兜底）
      - 用户回来后手动触发 `/review`
    - watcher 返回后，读取 `handoff/state.json` 确认状态
11. 等待 Cursor 期间，不依赖对话上下文短期记忆作为唯一上下文；当前任务状态以这些文件为准：
    - `handoff/current-task.md`
    - `handoff/cursor-prompt.md`
    - `handoff/state.json`
    - 当前仓库实际代码 diff
12. 当用户下一次回到当前仓库对话时，优先先检查 `handoff/state.json`：
    - 若状态仍是 `awaiting_cursor`，则继续等待
    - 若状态为 `review_ready`，默认直接进入 review，而不依赖用户必须说 `/review`
13. 进入 review 流程后：
    - 读取 `handoff/current-task.md`
    - 读取 `handoff/state.json`
    - 读取当前代码实际 diff
    - 对比是否满足 handoff 边界与自检要求
14. review 结束后，明确给出结论：
    - 通过 / 不通过
    - 若不通过，列出高置信问题与修正建议，并将 review 结果写入 `handoff/review-feedback.md`
    - 若不通过且需要 Cursor 修正，基于 review 结果生成修正 prompt 并 relay 回 Cursor（回到步骤 7）
    - 若通过，执行 `handoff_state.py mark-reviewed`，说明可继续下一步
