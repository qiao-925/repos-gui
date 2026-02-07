# 仓库完整性检查模块：使用 git fsck 验证仓库完整性
#
# 主要功能：
#   - check_repo()：检查单个仓库的完整性（git fsck）
#   - check_repos_parallel()：并行检查多个仓库
#
# 检查原理：
#   - 使用 git fsck --strict 检查 Git 对象完整性
#   - 检测损坏的对象、缺失的对象、无效的引用
#   - 忽略 dangling objects 警告（这是正常的）

import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from .process_control import (
    is_shutdown_requested,
    start_tracked_process,
    terminate_process,
    untrack_process,
)
from ..infra.logger import log_error, log_info, log_success, log_warning


def check_repo(repo_path: Path, repo_full: str, timeout: int = 30) -> Tuple[bool, Optional[str]]:
    """检查单个仓库的完整性（使用 git fsck）
    
    Args:
        repo_path: 仓库路径
        repo_full: 仓库全名（格式：owner/repo，用于日志）
        timeout: 超时时间（秒，默认：30）
    
    Returns:
        (是否有效, 错误信息)
    """
    # 检查是否是 Git 仓库
    if not (repo_path / ".git").exists():
        return False, "不是 Git 仓库（缺少 .git 目录）"

    if is_shutdown_requested():
        return False, "检查已取消（程序正在退出）"
    
    # 执行 git fsck 检查
    try:
        process = start_tracked_process(
            ['git', '-C', str(repo_path), 'fsck', '--no-progress', '--strict'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            stdout, stderr = process.communicate(timeout=timeout)
            result_return_code = process.returncode
        except subprocess.TimeoutExpired:
            terminate_process(process)
            return False, "检查超时"
        finally:
            untrack_process(process)

        if is_shutdown_requested():
            terminate_process(process)
            return False, "检查已取消（程序正在退出）"
        
        # git fsck 返回 0 表示没有错误
        if result_return_code == 0:
            return True, None
        
        # 返回非 0 表示有问题
        stderr = (stderr or "").strip()
        
        # 忽略常见的警告（dangling objects 是正常的）
        if 'dangling' in stderr.lower():
            # dangling objects 是正常的，不算错误
            return True, None
        
        # 其他错误都是严重问题
        error_msg = stderr[:200] if stderr else "未知错误"
        return False, error_msg
        
    except subprocess.TimeoutExpired:
        return False, "检查超时"
    except Exception as e:
        return False, f"检查失败: {e}"


def check_repos_parallel(
    tasks: List[Dict[str, str]],
    parallel_tasks: int = 5,
    timeout: int = 30,
    progress_cb: Optional[Callable[[int, int, int, int], None]] = None,
) -> Tuple[int, int, List[Dict[str, str]]]:
    """并行检查多个仓库
    
    Args:
        tasks: 任务列表，每个任务包含: repo_full, repo_name, group_folder
        parallel_tasks: 并行任务数（默认：5）
        timeout: 超时时间（秒，默认：30）
    
    Returns:
        (通过数, 失败数, 失败任务列表)
    """
    total = len(tasks)
    
    if total == 0:
        log_warning("没有需要检查的仓库")
        return 0, 0, []
    
    log_info(f"开始批量检查，共 {total} 个仓库")
    log_info(f"并行任务数: {parallel_tasks}")
    
    success_count = 0
    fail_count = 0
    failed_tasks = []

    if progress_cb:
        progress_cb(0, total, success_count, fail_count)
    
    with ThreadPoolExecutor(max_workers=parallel_tasks) as executor:
        future_to_task = {}
        for task in tasks:
            repo_path = Path(task['group_folder']) / task['repo_name']
            future = executor.submit(
                check_repo,
                repo_path,
                task['repo_full'],
                timeout
            )
            future_to_task[future] = task
        
        for future in as_completed(future_to_task):
            if is_shutdown_requested():
                log_warning("检测到程序退出请求，停止后续完整性检查收集")
                break
            task = future_to_task[future]
            try:
                is_valid, error_msg = future.result()
                if is_valid:
                    success_count += 1
                    log_success(f"检查通过: {task['repo_full']}")
                else:
                    fail_count += 1
                    failed_tasks.append(task)
                    log_error(f"检查失败: {task['repo_full']} - {error_msg}")
            except Exception as e:
                fail_count += 1
                failed_tasks.append(task)
                log_error(f"检查异常: {task['repo_full']} - {e}")

            if progress_cb:
                done = success_count + fail_count
                progress_cb(done, total, success_count, fail_count)
    
    log_info(f"并行检查完成，通过: {success_count}, 失败: {fail_count}")
    return success_count, fail_count, failed_tasks

