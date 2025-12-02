# 并行克隆控制模块
#
# 主要功能：
#   - execute_parallel_clone()：并行执行克隆任务
#   - 结果收集和统计

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

from lib.clone import clone_repo
from lib.logger import log_error, log_info, log_success, log_warning


def execute_parallel_clone(
    tasks: List[Dict[str, str]],
    parallel_tasks: int,
    parallel_connections: int
) -> Tuple[int, int, List[Dict[str, str]]]:
    """并行执行克隆任务
    
    Args:
        tasks: 任务列表，每个任务包含: repo_full, repo_name, group_folder, group_name, highland
        parallel_tasks: 并行任务数（同时克隆的仓库数量）
        parallel_connections: 并行传输数（每个仓库的 Git 连接数）
    
    Returns:
        (成功数, 失败数, 失败任务列表)
    """
    total = len(tasks)
    
    if total == 0:
        log_warning("没有需要克隆的仓库")
        return 0, 0, []
    
    log_info(f"开始批量克隆，共 {total} 个仓库")
    log_info(f"并行任务数: {parallel_tasks}, 并行传输数: {parallel_connections}")
    
    success_count = 0
    fail_count = 0
    failed_tasks = []
    
    # 使用线程池执行并行任务（自动管理并发数）
    with ThreadPoolExecutor(max_workers=parallel_tasks) as executor:
        # 提交所有任务
        future_to_task = {
            executor.submit(
                clone_repo,
                task['repo_full'],
                task['repo_name'],
                task['group_folder'],
                parallel_connections
            ): task
            for task in tasks
        }
        
        # 收集结果（按完成顺序）
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                success = future.result()
                if success:
                    success_count += 1
                    log_success(f"克隆成功: {task['repo_full']}")
                else:
                    fail_count += 1
                    failed_tasks.append(task)
                    log_error(f"克隆失败: {task['repo_full']}")
            except Exception as e:
                fail_count += 1
                failed_tasks.append(task)
                log_error(f"克隆异常: {task['repo_full']} - {e}")
    
    log_info(f"并行克隆执行完成，成功: {success_count}, 失败: {fail_count}")
    return success_count, fail_count, failed_tasks

