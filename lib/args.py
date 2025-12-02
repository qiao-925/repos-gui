# 命令行参数解析模块
#
# 主要功能：
#   - parse_args()：解析命令行参数
#   - 参数验证
#   - 帮助信息生成

import argparse
import sys
from pathlib import Path
from typing import Optional

from lib.logger import log_error


def validate_positive_int(value: str) -> int:
    """验证参数为正整数且 >= 1"""
    try:
        num = int(value)
        if num < 1:
            raise argparse.ArgumentTypeError(f"必须是正整数且 >= 1: {value}")
        return num
    except ValueError:
        raise argparse.ArgumentTypeError(f"必须是整数: {value}")


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="GitHub 仓库批量克隆脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                        # 使用默认参数，从 REPO-GROUPS.md 解析所有仓库
  %(prog)s -t 10 -c 16            # 并行任务数 10，并行传输数 16
  %(prog)s -f failed-repos.txt    # 从失败列表文件重新执行失败的仓库
  %(prog)s --check-only           # 只检查已存在的仓库，不执行克隆
  %(prog)s -f failed-repos.txt --check-only  # 检查失败列表中的仓库

任务列表文件格式（REPO-GROUPS.md 格式）:
  # GitHub 仓库分组
  
  仓库所有者: owner
  
  ## 分组名 <!-- 高地编号 -->
  - 仓库名1
  - 仓库名2

执行完成后，失败的仓库会自动保存到 failed-repos.txt（REPO-GROUPS.md 格式）
        """
    )
    
    parser.add_argument(
        '-t', '--tasks',
        type=validate_positive_int,
        default=5,
        metavar='NUM',
        help='并行任务数（同时克隆的仓库数量，默认: 5）'
    )
    
    parser.add_argument(
        '-c', '--connections',
        type=validate_positive_int,
        default=8,
        metavar='NUM',
        help='并行传输数（每个仓库的 Git 连接数，默认: 8）'
    )
    
    parser.add_argument(
        '-f', '--file',
        type=str,
        default=None,
        metavar='FILE',
        help='指定任务列表文件（REPO-GROUPS.md 格式）。如果不指定，默认从 REPO-GROUPS.md 解析'
    )
    
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='只检查已存在的仓库，不执行克隆'
    )
    
    args = parser.parse_args()
    
    # 验证文件参数（如果提供）
    if args.file is not None:
        file_path = Path(args.file)
        if not file_path.exists():
            log_error(f"任务列表文件不存在: {file_path}")
            sys.exit(1)
        if not file_path.is_file():
            log_error(f"不是有效的文件: {file_path}")
            sys.exit(1)
    
    return args

