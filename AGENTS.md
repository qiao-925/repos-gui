## 自动重打包与运行规则

- 对仓库进行任何代码改动后（`src/`、`gui.py`、`main.py`、`*.spec`），必须自动执行：
uv sync --group build
uv run pyinstaller --noconfirm --clean --onefile --windowed --name gh-repos-gui --paths src gui.py

根据当前操作系统决定执行

**Windows**
```
.\dist\gh-repos-gui.exe
```

**Linux / macOS**
```bash
chmod +x ./dist/gh-repos-gui && ./dist/gh-repos-gui

- 若只修改文档（如 `README.md`）可跳过。
- 若自动重打包失败，需返回错误原因并停止继续操作。

