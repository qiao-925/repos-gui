# 当前任务：CloneX 0.1.0 发布前校验

## 目标

对 CloneX 0.1.0 进行发布前全面校验，基于项目已有的 release gate 规则和业界标准，判断当前代码是否满足 PyPI 发布条件，给出明确的发布建议。

## 来源优先级
- P0：项目 release gate 规则（`.windsurf/rules/clonex-release-gate.mdc`）、当前代码、pyproject.toml
- P1：PEP 440、SemVer 2.0.0、Python Packaging User Guide、PyPI 发布最佳实践

## 已确认事实
- 当前版本 `0.1.0`，处于 `0.x` 预发布阶段
- 刚完成 `gh_repos_sync` → `clonex` 包名重命名
- `uv run --group test pytest -q` 通过 94 tests
- `uv build` 成功生成 `clonex-0.1.0.tar.gz` 和 `clonex-0.1.0-py3-none-any.whl`
- `uv run clonex --help` 正常输出
- 发布 workflow 仅支持 `workflow_dispatch` 手动触发
- README 已简化，GUI/MCP 标记为"待完善"
- 之前 v1.0.0~v1.0.3 的 tag 和 PyPI 发布已被回退

## 稳定区域
- 不修改任何代码逻辑
- 不修改版本号
- 不执行实际发布动作
- 不创建 tag 或 GitHub Release

## 预期交付
- 按 release gate 规则逐项校验，输出 Release Gate 评估报告
- 列出通过项、未通过项、需补充项
- 给出明确结论：建议发布 / 延缓发布
- 列出需要用户确认的动作（如有）
