# 路径处理模块：提供路径和目录处理功能
#
# 主要功能：
#   - 获取脚本目录（SCRIPT_DIR）
#   - 获取仓库目录（REPOS_DIR）
#   - 获取临时目录（跨平台兼容）

import os
import sys
import tempfile
from pathlib import Path


def get_script_dir() -> Path:
    """获取脚本所在目录"""
    # PyInstaller onefile：使用可执行文件所在目录
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()

    # 源码运行：使用项目根目录
    return Path(__file__).resolve().parents[3]


def get_repos_dir() -> Path:
    """获取仓库目录（REPOS_DIR）
    
    仓库目录放在项目目录的上一级（同级目录）
    SCRIPT_DIR 已经是项目目录，所以上一级是 SCRIPT_DIR/..
    """
    script_dir = get_script_dir()
    # 上一级目录的 repos 子目录
    return script_dir.parent / "repos"


# 全局路径常量
SCRIPT_DIR = get_script_dir()
REPOS_DIR = get_repos_dir()

