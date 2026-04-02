# 构建和发布指南

## 自动构建

项目已配置 GitHub Actions 自动构建，支持跨平台发布：

### 触发方式
1. **标签推送**：推送 `v*` 标签（如 `v1.0.0`）会自动构建并创建 Release
2. **手动触发**：在 GitHub Actions 页面手动运行 "Build and Release" 工作流

### 支持平台
- Windows (`.exe`)
- macOS (可执行文件)
- Linux (可执行文件)

### 构建产物
构建完成后，可执行文件会自动上传到 GitHub Release，用户可直接下载使用，无需克隆仓库或安装依赖。

## 本地构建

如需本地构建，请确保已安装 uv：

```bash
# 安装依赖
uv sync --group build

# 构建
uv run pyinstaller --noconfirm --clean --onefile --windowed --name gh-repos-gui --paths src gui.py

# 运行
./dist/gh-repos-gui  # Linux/macOS
./dist/gh-repos-gui.exe  # Windows
```

## 发布新版本

1. 更新版本号（如有需要）
2. 提交代码：`git commit -m "Release v1.0.0"`
3. 创建标签：`git tag v1.0.0`
4. 推送标签：`git push origin v1.0.0`

GitHub Actions 会自动构建并创建 Release。
