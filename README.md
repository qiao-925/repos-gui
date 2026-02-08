# GitHub 仓库批量管理工具（GUI）

用于 GitHub 仓库批量管理的桌面 GUI 工具，提供仓库同步、分类维护、批量克隆、批量更新和失败重试能力。减少重复命令操作，提升多仓库日常维护效率。

## 核心功能

- **仓库同步与分类管理**：同步 GitHub 仓库列表，支持 AI 全量分类、增量归档到 `未分类` 及手动维护。
- **批量执行与一致性校验**：按分组并行克隆并执行 `git fsck` 校验，支持已克隆仓库批量更新（`git pull --ff-only`）。
- **失败追踪与重试闭环**：自动记录失败任务清单，支持一键重试与执行结果回溯。

## Quick Start

### 打包

```bash
uv sync --group build
uv run pyinstaller --noconfirm --clean --onefile --windowed --name gh-repos-gui --paths src gui.py
```

### 启动

**Windows**

```powershell
.\dist\gh-repos-gui.exe
```

**Linux / macOS**

```bash
chmod +x ./dist/gh-repos-gui && ./dist/gh-repos-gui
```

## 项目结构

```text
.
├─ gui.py                           # GUI 启动入口（开发运行）
├─ gh-repos-gui.spec                # PyInstaller 构建配置
├─ scripts/
│  ├─ rebuild-run.ps1               # 一键重打包并运行（Windows）
│  └─ watch-rebuild-run.ps1         # 监听文件变化后重打包运行
└─ src/
   └─ gh_repos_sync/
      ├─ ui/                        # 界面与交互层
      │  ├─ main_window.py          # 主窗口与主流程入口
      │  ├─ workers.py              # 后台任务线程（避免阻塞 UI）
      │  ├─ theme.py                # 主题样式配置
      │  └─ chrome.py               # 窗口外观相关
      ├─ application/               # 用例编排层
      │  ├─ ai_generation.py        # AI 分类流程编排
      │  └─ execution.py            # 克隆/更新执行流程编排
      ├─ core/                      # 核心能力层
      │  ├─ repo_config.py          # 分组文件读取、写入与同步逻辑
      │  ├─ clone.py                # 单仓库克隆
      │  ├─ pull.py                 # 单仓库更新
      │  ├─ parallel.py             # 并行任务调度
      │  ├─ check.py                # 仓库完整性校验（git fsck）
      │  ├─ failed_repos.py         # 失败仓库记录与输出
      │  └─ process_control.py      # 执行过程控制
      ├─ domain/                    # 领域规则层
      │  ├─ models.py               # 领域模型定义
      │  └─ repo_groups.py          # 分组解析与渲染规则
      └─ infra/                     # 基础设施接入层
         ├─ auth.py                 # GitHub 授权
         ├─ github_api.py           # GitHub API 调用封装
         ├─ ai.py                   # DeepSeek API 调用封装
         ├─ logger.py               # 日志输出
         └─ paths.py                # 运行路径与配置路径
```

依赖方向：`ui -> application -> core/domain -> infra`

## 依赖

- Python `>=3.8`
- `PyQt5`
- `qt-material`
- `keyring`
- `colorama`（仅 Windows）
- `pyinstaller`（仅打包时需要）
