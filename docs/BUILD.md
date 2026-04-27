# 构建 GUI 可执行文件

本页只讲 GUI 打包，不描述 PyPI 发布流程。PyPI 发布是独立流程，见 `README.md` 的“发布到 PyPI”章节。

## GitHub Actions 构建

仓库中有一个 GUI 构建 workflow，用于生成桌面可执行文件并上传 GitHub Release 附件：

- `.github/workflows/build.yml`
- 支持 `v*` tag 触发，也支持手动 `workflow_dispatch`
- 产物是 `CloneX.exe` 或对应平台的可执行文件
- release 步骤只负责把构建产物挂到 GitHub Release，并不负责 PyPI 发布

## 本地构建

如需本地构建，请确保已安装 uv：

```bash
uv sync --group build
uv run pyinstaller --noconfirm --clean --onefile --windowed --name CloneX --paths src gui.py
```

构建产物默认位于 `dist/`：

- Windows：`dist/CloneX.exe`
- Linux / macOS：`dist/CloneX`

## 与 PyPI 发布的区别

- **GUI 构建**：用于生成桌面可执行文件，走 `build.yml`
- **PyPI 发布**：用于发布 Python 包，走 `.github/workflows/pypi-publish.yml`
- `pypi-publish.yml` 仅支持手动 `workflow_dispatch`
- 当前仓库版本仍处于 `0.x` 阶段，不应把 GUI 构建误写成自动发 PyPI 的流程
