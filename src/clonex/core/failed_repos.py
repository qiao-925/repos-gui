# 失败列表生成模块
#
# 主要功能：
#   - save_failed_repos()：保存失败的仓库列表为 REPO-GROUPS.md 格式

import re
from pathlib import Path
from typing import Dict, List

from ..domain.models import RepoTask
from ..domain.repo_groups import build_failed_repo_groups_text
from ..infra.logger import log_info, log_warning


def extract_highland_from_folder(group_folder: str) -> str:
    """从 group_folder 中提取高地编号
    
    Args:
        group_folder: 分组文件夹路径（格式：组名 (高地编号)）
    
    Returns:
        高地编号（如果存在），否则返回空字符串
    """
    # 正则表达式：匹配 (高地编号) 格式
    pattern = r'\(([^)]+)\)'
    match = re.search(pattern, group_folder)
    if match:
        return match.group(1).strip()
    return ''


def save_failed_repos(
    failed_tasks: List[Dict[str, str]],
    failed_repos_file: Path,
    repo_owner: str
) -> None:
    """保存失败的仓库列表为 REPO-GROUPS.md 格式
    
    Args:
        failed_tasks: 失败的任务列表
        failed_repos_file: 失败列表文件路径
        repo_owner: 仓库所有者
    
    Note:
        如果 failed_tasks 为空，不会创建文件（文件应该已经在执行开始时被清空）
    """
    if not failed_tasks:
        # 如果没有失败任务，确保文件不存在
        if failed_repos_file.exists():
            try:
                failed_repos_file.unlink()
            except Exception:
                pass  # 忽略删除失败
        return
    
    normalized_tasks: List[RepoTask] = []
    for task in failed_tasks:
        highland = task.get('highland', '')
        if not highland:
            highland = extract_highland_from_folder(task['group_folder'])

        normalized_tasks.append(
            RepoTask(
                repo_full=task['repo_full'],
                repo_name=task['repo_name'],
                group_folder=task['group_folder'],
                group_name=task['group_name'],
                highland=highland,
            )
        )

    content = build_failed_repo_groups_text(normalized_tasks, repo_owner)
    
    # 写入文件
    try:
        failed_repos_file.write_text(content, encoding='utf-8')
        
        log_warning(f"有 {len(failed_tasks)} 个仓库克隆失败")
        log_info(f"失败列表已保存到: {failed_repos_file}（REPO-GROUPS.md 格式）")
        log_info("可在 GUI 中选择该文件重新执行失败的仓库")
    except Exception as e:
        log_warning(f"保存失败列表失败: {failed_repos_file} - {e}")
