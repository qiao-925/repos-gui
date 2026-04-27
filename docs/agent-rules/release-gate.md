# CloneX Release Gate Rule

## Public Contract

发布评估时，以下都属于 CloneX 的公共契约：

- CLI 命令、参数、默认值和输出路径含义
- `REPO-GROUPS.md` Gist 格式和自动维护行规范
- PyPI 包名、extras、entry points
- MCP tools 名称、参数、响应结构
- GUI 启动入口和安装方式

在 `0.x` 阶段可以调整公共契约，但必须在 README 或 release notes 中明确说明破坏性影响。进入 `1.0.0` 后，破坏这些契约应进入 major release 评估。

## PyPI 发布门禁

发布到正式 PyPI 前，Agent 必须先完成并报告以下检查：

1. 版本符号符合当前阶段与 PEP 440，不复用已发布版本。
2. README 包含安装、CLI 快速开始、验证和发布说明。
3. `uv run --group test pytest -q` 通过。
4. `uv build` 成功生成 sdist 和 wheel。
5. 至少验证 `clonex --help` 可运行。
6. 对 CLI 主路径变更，必须说明是否已做真实低并可 smoke，或明确为何暂不做。
7. 发布 workflow 不应通过 tag / GitHub Release 自动触发正式 PyPI，除非用户明确要求恢复自动化。
8. 正式发布前必须向用户确认，不得擅自发布 PyPI。

## GitHub Release 与 Tag 规则

- 根据 GitHub Releases 文档，GitHub Release 基于 Git tag，代表一个可供用户下载和引用的源码快照。
- 在当前策略下，tag 不自动触发 PyPI 发布。
- 创建 `v*` tag 前，必须确认对应版本已经通过 PyPI 发布门禁。
- 删除或重写 tag 属于高风险操作，必须先说明影响并获得用户明确确认。

## TestPyPI 策略

当前 CloneX 策略是不使用 TestPyPI，全部走正式 PyPI 的手动发布流程。
如果未来要恢复 TestPyPI，必须先更新本规则和发布 workflow，并分开：
- `TEST_PYPI_API_TOKEN`
- `PYPI_API_TOKEN`

不得混用两个 token。

## 版本递增判断

| 变更类型 | `0.x` 推荐 | `1.0` 后推荐 |
|---|---|---|
| 文档、小修正 | patch，例如 `0.1.1` | patch，例如 `1.0.1` |
| CLI bugfix | patch | patch |
| CLI 新功能 | minor，例如 `0.2.0` | minor，例如 `1.1.0` |
| CLI 参数含义改变 | minor，并说明破坏性 | major |
| Gist 格式改变 | minor，并说明迁移影响 | major，除非完全兼容 |
| MCP tool 新增 | minor | minor |
| MCP tool 删除/改名 | minor，并说明破坏性 | major |
| GUI 可视化增强 | minor | minor |
| 安全修复 | patch，并说明风险 | patch，必要时允许兼容性例外 |

此表采用类似 SemVer：patch 表示 bugfix，minor 表示兼容性新增，major 表示不兼容公共契约变更。由于 CloneX 尚处 `0.x`，允许更快速迭代，但必须在 README 或 release notes 中说明破坏性影响。

## Agent 行为要求

当用户提出"发布"、"发版"、"打 tag"、"上 PyPI"、"改版本号"时，Agent 必须：
1. 先识别发布目的：CLI 试用、正式 PyPI、GitHub Release、0.x 权宜或稳定版。
2. 先做门禁评估，再改版本号或执行发布动作。
3. 优先保持 CLI 主路径简单可用，不把 GUI/MCP 的复杂度压进 CLI。
4. 对 GUI / MCP 的变更，明确其职责边界，不影响 CLI 快速上手门槛。
5. 对高风险操作（发布 PyPI、删 tag、改历史）必须单独请求确认。
6. 输出结果时必须说明：当前版本阶段、已通过检查、未完成检查、是否建议发布。

## 禁止事项

- 禁止在用户未明确确认时发布正式 PyPI。
- 禁止把未充分验证的版本标记为 `1.0.0`。
- 禁止通过 tag 或 GitHub Release 自动发布正式 PyPI，除非规则和 workflow 已明确恢复该策略。
- 禁止复用已发布到 PyPI 的版本号。
- 禁止把 CLI 做成复杂管理工具；复杂管理优先放到 GUI，Agent 自动化优先放到 MCP。

## 推荐发布评估输出模板

```md
## Release Gate

- **目标版本**：0.1.0
- **发布目标**：正式 PyPI / GitHub Release / 仅 tag / 不发布
- **版本阶段判断**：0.x 预发布，公共契约尚未稳定
- **CLI 主路径**：通过 / 未测试 / 未执行
- **测试**：通过 / 未通过 / 未执行
- **构建**：通过 / 未通过 / 未执行
- **README**：已覆盖 / 需补充
- **Smoke**：已执行 / 建议执行 / 暂不需要
- **风险**：...
- **结论**：建议发布 / 延缓发布
- **需要用户确认的动作**：...
```
