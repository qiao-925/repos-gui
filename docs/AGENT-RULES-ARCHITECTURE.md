# CloneX Agent Rules Architecture

## 概述

CloneX 采用**平台无关规则 + 桥接工具**的架构，避免被特定 AI 工具（Cursor、Windsurf 等）绑定，同时保留工具的可执行功能。

## 架构设计

```
docs/agent-rules/          # 平台无关规则源（单一真相源，版本控制）
    ↓ 同步
docs/agent-rules/          # 规则内容再生成到 .cursor/ 与 .windsurf/ 等工具目录
├── agent-workflow.md      # Agent 执行规则
├── release-gate.md        # 发布评估规则
├── handoff.md             # Handoff 工作流
└── review.md              # Review 工作流
    ↓ 同步脚本
.cursor/rules/             # Cursor 特定配置（可选，提供可执行功能）
├── agent-workflow.mdc     # 包含 frontmatter + 规则内容

.windsurf/rules/           # Windsurf 特定配置（可选，提供可执行功能）
├── clonex-release-gate.mdc # 包含 frontmatter + 规则内容

.windsurf/workflows/       # Windsurf 工作流（可选，提供 /handoff、/review 等命令）
├── handoff.md             # 包含 frontmatter + 规则内容
└── review.md              # 包含 frontmatter + 规则内容
```

## 核心原则

1. **单一真相源**：`docs/agent-rules/*.md` 存储纯 Markdown 规则，无工具特定 frontmatter
2. **平台边界**：规则源保留在仓库文档中，再由同步脚本生成各工具目录所需的配置文件
3. **桥接工具**：`scripts/sync-agent-rules.py` 将规则转换为工具特定格式
4. **可选增强**：工具特定配置提供可执行功能（如 /handoff、/review 命令）
5. **可迁移性**：规则内容不依赖任何工具，可轻松迁移到其他工具

## 为什么需要桥接工具

**纯文档模式（docs/agent-rules/ + 同步脚本）**：
- ✅ 优点：完全平台无关，规则源集中维护
- ❌ 缺点：无法直接提供工具特定功能（如 Windsurf 的 /handoff 命令）

**工具特定配置（.cursor/、.windsurf/）**：
- ✅ 优点：提供可执行功能（workflows、slash commands）
- ❌ 缺点：被工具绑定，需要维护工具特定格式

**桥接工具方案**：
- ✅ 结合两者优势：保持平台无关性，享受工具特性
- ✅ 单一真相源：规则只在 `docs/agent-rules/` 维护
- ✅ 自动化：通过脚本生成工具配置，避免重复

## 使用方式

### 场景 1：仅修改规则内容

```bash
# 1. 编辑规则文件
vim docs/agent-rules/agent-workflow.md

# 2. 同步到工具目录（如需工具特定功能）
python scripts/sync-agent-rules.py

# 3. 提交变更
git add docs/agent-rules/ .cursor/ .windsurf/
git commit -m "Update agent workflow rule"
```

### 场景 2：首次设置或迁移到新环境

```bash
# 克隆仓库后，一次性生成工具配置
python scripts/sync-agent-rules.py
```

### 场景 3：不使用工具特定功能（纯文档模式）

- 只需维护 `docs/agent-rules/` 和同步脚本生成的工具配置
- AI 工具按各自支持的入口读取对应配置
- 不需要运行同步脚本

### 场景 4：检查配置是否同步

```bash
# 检查生成的文件是否是最新的（不修改文件）
python scripts/sync-agent-rules.py --check
```

## 自动化选项

### CI/CD 集成（可选）

在 `.github/workflows/` 中添加：

```yaml
- name: Sync agent rules
  run: python scripts/sync-agent-rules.py
```

### Pre-commit Hook（可选）

在 `.git/hooks/pre-commit` 中添加：

```bash
python scripts/sync-agent-rules.py --check
```

## 版本控制策略

**推荐方案**：
- `docs/agent-rules/` 纳入版本控制（必须）
- `scripts/sync-agent-rules.py` 纳入版本控制（必须）
- `.cursor/` 和 `.windsurf/` 由脚本生成或同步

**理由**：
- 工具特定配置是生成的，不应手动编辑
- 避免 merge 冲突
- 新环境克隆后只需运行一次脚本

## 扩展到其他工具

如需支持其他工具（如 Claude Code、VS Code Copilot 等），只需：

1. 在 `scripts/sync-agent-rules.py` 中添加新的生成函数
2. 定义该工具的 frontmatter 格式
3. 添加到 `rule_mappings` 配置中

示例：

```python
def write_claude_rule(source_path: Path, target_path: Path):
    """Write Claude-specific CLAUDE.md file."""
    content = read_source_file(source_path)
    # Claude 无需 frontmatter，直接复制
    target_path.write_text(content, encoding="utf-8")
```

## 相关工具参考

- [dotagent](https://github.com/johnlindquist/dotagent) - 通用 AI agent 配置管理器
- [agent-rules-kit](https://github.com/tecnomanu/agent-rules-kit) - 规则转换工具

## 维护指南

### 添加新规则

1. 在 `docs/agent-rules/` 创建新的 `.md` 文件
2. 在仓库入口文档或同步配置中添加引用说明
3. 在 `scripts/sync-agent-rules.py` 的 `rule_mappings` 中添加映射
4. 运行 `python scripts/sync-agent-rules.py` 生成工具特定配置

### 修改规则

1. 直接编辑 `docs/agent-rules/*.md`
2. 运行 `python scripts/sync-agent-rules.py` 同步（如需工具特定功能）
3. 提交 `docs/agent-rules/` 的变更

### CI/CD 集成

在 `.github/workflows/` 中添加：

```yaml
- name: Sync agent rules
  run: python scripts/sync-agent-rules.py
```

## 优势

- **平台无关**：规则内容不依赖任何工具
- **可迁移**：轻松迁移到其他工具
- **可维护**：单一真相源，避免重复
- **可重现**：通过脚本自动生成配置
- **可扩展**：轻松添加对新工具的支持
- **功能完整**：保留工具的可执行功能（workflows、slash commands）
