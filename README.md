# GitHub 仓库批量管理工具（GUI）

## 快速打包

```
uv sync --group build
uv run pyinstaller --noconfirm --clean --onefile --windowed --name gh-repos-gui --paths src gui.py
```

单页 GUI 工具，覆盖 **同步 / AI 分类 / 批量克隆 / 批量更新 / 失败重试**。

## 快速开始

先在当前平台执行“快速打包”命令，再运行 `dist/` 下生成的可执行文件。

**Windows**
```
.\dist\gh-repos-gui.exe
```

**Linux / macOS**
```bash
chmod +x ./dist/gh-repos-gui && ./dist/gh-repos-gui
```

> 首次运行需要登录 GitHub 授权，以获取仓库列表。

## 功能概览

| 功能 | 说明 |
|------|------|
| AI 自动分类（全量） | 调用 DeepSeek API 重建分类（会覆盖现有分组结果） |
| 增量更新到未分类 | 自动发现新增仓库并写入 `未分类`，用于日常增量维护 |
| 手动分类 | 直接编辑 REPO-GROUPS.md 文件进行手动整理 |
| 批量克隆 | 按分组并行克隆仓库，已存在且完整的仓库自动跳过 |
| 克隆后完整性校验 | 克隆完成后自动执行 `git fsck` 校验，失败会计入失败清单 |
| 批量更新已克隆仓库 | 对本地已克隆仓库并行执行 `git pull --ff-only` |
| 失败重试（一键） | 自动生成 `failed-repos.txt`，支持按钮一键重试失败仓库 |
| 执行进度条 | 显示阶段（克隆/校验/更新）、完成数、成功数、失败数 |
| 运行中停止 | 克隆/批量更新执行中可点击「停止」，后台任务会收到终止请求 |
| 结果汇总与失败原因 | 执行结束弹出成功率汇总；批量更新失败会在日志输出失败原因 |

## 使用流程

```
1. 登录 GitHub  →  2. 分类（AI全量 / 增量更新 + 手动微调）  →  3. 开始克隆 / 批量更新 / 失败重试
```

- 首次建档建议：`AI 自动分类（全量）` → 手动微调 → 开始克隆
- 日常维护建议：`增量更新到未分类` → 手动微调 → 开始克隆 → 批量更新已克隆仓库

## 登录授权

已内置 OAuth App Client ID，点击「登录 GitHub」按钮即可唤起浏览器完成授权。

- Token 默认存储在系统钥匙串（Keyring），不可用时回退到本地配置文件
- AI 分类需要 DeepSeek API Key（首次使用时输入，支持保存到钥匙串）
- AI 分类 System Prompt 已独立为可编辑文件：`%APPDATA%/gh-repos-gui/ai_classify_system_prompt.txt`（Windows）
- 分类面板提供「编辑 AI Prompt」按钮，可直接打开修改
- 主界面执行 AI 全量分类前会弹出覆盖警示，并自动尝试备份现有 `REPO-GROUPS.md`

## 默认参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 并行任务数 | 5 | 同时克隆的仓库数量 |
| 并行连接数 | 8 | 每个克隆任务的连接数 |
| 检查超时 | 30 秒 | git fsck 超时时间（固定） |

## 配置文件格式

任务列表文件 `REPO-GROUPS.md` 格式如下：

```markdown
# GitHub 仓库分组

仓库所有者: your-username

## Go-Practice <!-- 397.8号高地 -->
- go-admin
- go-zero

## Java-Practice <!-- 597.9号高地 -->
- incubator-seata
- spring-boot
```

- 每个 `##` 标题为一个分组
- `<!-- -->` 注释为可选的高地编号标签
- 每个 `-` 开头的行为一个仓库名

## AI Prompt 自定义

- 默认 Prompt 文件路径：
  - Windows: `%APPDATA%/gh-repos-gui/ai_classify_system_prompt.txt`
  - macOS: `~/Library/Application Support/gh-repos-gui/ai_classify_system_prompt.txt`
  - Linux: `${XDG_CONFIG_HOME:-~/.config}/gh-repos-gui/ai_classify_system_prompt.txt`
- 首次点击「编辑 AI Prompt」或首次执行 AI 分类时，会自动创建默认 Prompt 模板。
- 模板中的 `{{ALLOWED_GROUPS}}` 会在运行时自动替换为当前分组列表。
- 模板中的 `{{MAX_GROUPS}}` 会在运行时自动替换为分类上限（当前为 `10`）。
- 即使你移除了该占位符，程序也会在 Prompt 末尾自动补充分组提示。
- 程序端有兜底后处理：优先做仓库名前缀归并（如 `abc-api` / `abc-web`），并强制将最终分组数限制在 10 以内。

## 克隆输出目录

默认输出到脚本目录上一级的 `repos/` 文件夹：

```
../repos/组名 (高地编号)/仓库名
```

## 从源码运行

```bash
# 使用 uv 安装依赖（推荐）
uv sync

# 运行 GUI
uv run python gui.py
```

兼容旧流程（不推荐）：

```bash
pip install -r requirements.txt
python gui.py
```

## 构建可执行文件

```
uv sync --group build
uv run pyinstaller --noconfirm --clean --onefile --windowed --name gh-repos-gui --paths src gui.py
```

- 构建产物：`dist/gh-repos-gui.exe`
- 说明：可执行文件是平台相关产物（Windows/macOS/Linux 不通用），建议在目标平台本地打包本地使用，不提交到仓库。

## 项目结构（按流程粗粒度）

```
src/
  gh_repos_sync/
    ui/                  # 界面层：只负责交互与显示
      main_window.py     # 主流程页面（登录→分类→同步→克隆/更新/重试）
      dialogs.py         # 分类编辑对话框
      workers.py         # 后台线程（避免阻塞 UI）
      theme.py           # 主题样式
      chrome.py          # 图标/标题栏外观

    application/         # 用例层：按业务流程编排
      ai_generation.py   # 分类流程：拉仓库 + AI 分类 + 写入分组文件
      execution.py       # 执行流程：克隆+校验 / 批量更新

    core/                # 核心能力层：高复用、本地规则
      repo_config.py     # REPO-GROUPS 读写、owner 读写、同步预览/应用
      clone.py           # 单仓库克隆
      pull.py            # 单仓库更新（git pull）
      parallel.py        # 并行克隆调度
      check.py           # 仓库完整性检查（git fsck）
      failed_repos.py    # 失败任务文件生成

    domain/              # 领域规则层：纯规则、无外部依赖
      models.py          # RepoTask 领域模型
      repo_groups.py     # 分组解析/渲染规则

    infra/               # 基础设施层：外部系统接入
      auth.py            # GitHub 设备码授权
      github_api.py      # GitHub API 调用
      ai.py              # DeepSeek API 调用
      logger.py          # 日志输出
      paths.py           # 路径与运行环境

gui.py                   # GUI 启动入口（开发运行）
main.py                  # 兼容入口
README.md
```

### 依赖方向

- `ui -> application -> core/domain -> infra`
- `ui` 不直接承载复杂业务编排，复杂流程在 `application`
- `core` 负责可复用能力，避免“一个函数一个文件”的碎片化
- `domain` 只放规则与模型，不关心 UI / API
- `infra` 只做外部接入，不做业务决策

### 三条主流程对应模块

- 登录授权：`ui/main_window.py` + `ui/workers.py` + `infra/auth.py`
- 仓库分类：`ui/dialogs.py` + `application/ai_generation.py` + `core/repo_config.py`
- 克隆校验：`application/execution.py` + `core/clone.py` + `core/parallel.py` + `core/check.py`
- 批量更新：`application/execution.py` + `core/pull.py`

## 依赖

- Python 3.8+
- PyQt5
- qt-material（Material Design 主题）
- keyring（系统钥匙串存储）
- colorama（终端颜色支持）

## 备注

- 同步功能仅写入新增仓库，不处理删除/改名/转移
- 失败列表格式与 REPO-GROUPS.md 相同，可直接作为任务文件使用
