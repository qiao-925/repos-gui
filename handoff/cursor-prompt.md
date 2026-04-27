## Task
对 CloneX 0.1.0 进行发布前全面校验，基于项目 release gate 规则和业界标准判断是否满足 PyPI 发布条件，输出 Release Gate 评估报告。

## Context
- 项目 release gate 规则：`.windsurf/rules/clonex-release-gate.mdc:1-136`
  - 定义了公共契约、版本阶段规则、PyPI 发布门禁 8 项检查、GitHub Release/Tag 规则
  - 推荐发布评估输出模板在 `:119-135`
- 当前版本：`0.1.0`（`0.x` 预发布阶段），`pyproject.toml:7`
- 刚完成 `gh_repos_sync` → `clonex` 包名重命名，所有 import 路径已更新
- 已知已通过项：
  - `uv run --group test pytest -q`：94 passed
  - `uv build`：成功生成 `clonex-0.1.0.tar.gz` + `clonex-0.1.0-py3-none-any.whl`
  - `uv run clonex --help`：正常输出
- 发布 workflow：`.github/workflows/pypi-publish.yml:1-34`，仅 `workflow_dispatch` 手动触发
- README：`README.md:1-76`，已简化，GUI/MCP 标记为"待完善"
- 之前 v1.0.0~v1.0.3 的 tag 和 PyPI 发布已被回退，当前 PyPI 上无任何版本

## Source of truth
- P0：`.windsurf/rules/clonex-release-gate.mdc`、当前代码、`pyproject.toml`
- P1：PEP 440、SemVer 2.0.0、Python Packaging User Guide

## Stable boundaries
- 不修改任何代码逻辑
- 不修改版本号
- 不执行实际发布动作
- 不创建 tag 或 GitHub Release

## What to change
### 步骤 1：调研业界标准
1. 调研 PEP 440 版本号规范，确认 `0.1.0` 是否合规
2. 调研 PyPI 发布最佳实践（README 质量、元数据完整性、license 文件等）
3. 调研 SemVer 2.0.0 对 `0.x` 阶段的要求
4. 调研 Python Packaging User Guide 对 sdist/wheel 的要求

### 步骤 2：逐项校验 release gate 门禁
5. 按 `.windsurf/rules/clonex-release-gate.mdc:56-67` 的 8 项门禁逐项检查：
   - 门禁 1：版本符号符合当前阶段与 PEP 440，不复用已发布版本
   - 门禁 2：README 包含安装、CLI 快速开始、验证和发布说明
   - 门禁 3：`uv run --group test pytest -q` 通过
   - 门禁 4：`uv build` 成功生成 sdist 和 wheel
   - 门禁 5：至少验证 `clonex --help` 可运行
   - 门禁 6：CLI 主路径变更，是否已做真实 smoke，或明确为何暂不做
   - 门禁 7：发布 workflow 不应通过 tag/GitHub Release 自动触发正式 PyPI
   - 门禁 8：正式发布前必须向用户确认

### 步骤 3：补充校验
6. 检查 `pyproject.toml` 元数据完整性（classifiers、license、urls、description）
7. 检查 `LICENSE` 文件是否存在
8. 检查 `MANIFEST.in` 或 `pyproject.toml` 的 sdist 包含配置是否合理
9. 检查 `README.md` 是否覆盖安装、使用、验证步骤
10. 检查 `docs/` 文档与代码的一致性（特别是 `docs/MCP-GUIDE.md` 工具清单 vs 实际代码）
11. 检查 `docs/ARCHITECTURE.md` 中是否还有过时的 `gh_repos_sync` 引用或指向不存在的文件
12. 检查 `docs/BUILD.md` 和 `docs/GIST-CONFIG-GUIDE.md` 是否有过时描述

### 步骤 4：输出评估报告
13. 按 `.windsurf/rules/clonex-release-gate.mdc:119-135` 的模板格式输出 Release Gate 评估报告
14. 对每项给出：通过 / 未通过 / 需补充 / 不适用
15. 给出明确结论：建议发布 / 延缓发布
16. 列出需要用户确认的动作

### 自检
17. 确认报告覆盖了 release gate 的全部 8 项门禁
18. 确认报告引用的标准来源可溯源（P0/P1 标注）

## Expected result
- 一份完整的 Release Gate 评估报告，覆盖 release gate 8 项门禁 + 补充校验项
- 每项有明确的通过/未通过判断
- 有明确的发布建议结论
- 有需要用户确认的动作清单

## Validation
1. 报告覆盖 release gate 全部 8 项门禁
2. 报告引用的标准来源可溯源
3. 结论明确：建议发布或延缓发布

## Completion callback
完成所有改动并通过自检后，**必须**执行：
```
python scripts/handoff_state.py detect
```
这会将 `handoff/state.json` 从 `awaiting_cursor` 更新为 `review_ready`，通知发起方可以开始 review。
- 只有完成本轮目标文件修改后才能执行此命令
- 不要写入 `reviewed`，该状态只由 review 方写入

## Do NOT
- 不要修改任何代码逻辑
- 不要修改版本号
- 不要执行实际发布动作
- 不要创建 tag 或 GitHub Release
- 不要新增 Python 依赖
- 不要修改 `.github/workflows/` 的实际行为
- 不要修改 `pyproject.toml` 中的版本号
