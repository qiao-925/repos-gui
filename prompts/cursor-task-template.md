## Task
[一句话描述目标]

## Context
- 相关文件：`path/to/file.ts:23-45`
- 依赖关系：[X 调用 Y，Y 在 path/to/y.ts]
- 现有约定：[命名规范、架构分层等]

## What to change
1. 在 `path/to/file.ts` 第 X 行，将 `foo()` 改为 `bar(options)`
2. 在 `path/to/other.ts` 新增函数 `baz`，签名为：`...`
3. 不要动 `path/to/stable.ts`

## Expected result
[改完后的行为/输出]

## Completion callback
完成所有改动并通过自检后，**必须**执行：
```
python scripts/handoff_state.py detect
```
这会将 `handoff/state.json` 从 `awaiting_cursor` 更新为 `review_ready`，通知发起方可以开始 review。
- 只有完成本轮目标文件修改后才能执行此命令
- 不要写入 `reviewed`，该状态只由 review 方写入

## Do NOT
- 不要重构无关代码
- 不要新增依赖
