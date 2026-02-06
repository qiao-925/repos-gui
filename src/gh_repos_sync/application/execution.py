"""Application services for clone/check execution flows."""

import time
from pathlib import Path
from typing import Dict, Tuple

from ..core import repo_config
from ..core.check import check_repos_parallel
from ..core.failed_repos import save_failed_repos
from ..core.parallel import execute_parallel_clone

CHECK_TIMEOUT = 30
FAILED_REPOS_FILE: Path = repo_config.SCRIPT_DIR / "failed-repos.txt"


def run_clone_and_check(
    config_file: str,
    tasks: int,
    connections: int,
    failed_repos_file: Path = FAILED_REPOS_FILE,
    check_timeout: int = CHECK_TIMEOUT,
) -> Tuple[bool, Dict[str, int], str]:
    """Run clone then integrity check, returning a UI-friendly summary."""
    try:
        start_time = time.time()
        parsed_tasks = repo_config.parse_repo_groups(config_file)
        if not parsed_tasks:
            raise ValueError("未找到任何仓库任务")

        total_repos = len(parsed_tasks)

        if failed_repos_file.exists():
            try:
                failed_repos_file.unlink()
            except Exception:
                pass

        success_count, fail_count, failed_tasks = execute_parallel_clone(
            parsed_tasks,
            tasks,
            connections,
        )

        if success_count > 0:
            successful_tasks = [task for task in parsed_tasks if task not in failed_tasks]
            _, _, check_failed_tasks = check_repos_parallel(
                successful_tasks,
                parallel_tasks=tasks,
                timeout=check_timeout,
            )

            if check_failed_tasks:
                failed_tasks.extend(check_failed_tasks)
                fail_count += len(check_failed_tasks)
                success_count -= len(check_failed_tasks)

        if failed_tasks:
            save_failed_repos(
                failed_tasks,
                failed_repos_file,
                repo_config.REPO_OWNER or "qiao-925",
            )

        result = {
            "total": total_repos,
            "success": success_count,
            "fail": fail_count,
            "duration": int(time.time() - start_time),
            "failed_file": str(failed_repos_file) if failed_tasks else "",
        }
        return True, result, ""

    except SystemExit:
        return False, {}, "配置文件解析失败"
    except Exception as e:
        return False, {}, str(e)


def run_check_only(
    config_file: str,
    tasks: int,
    failed_repos_file: Path = FAILED_REPOS_FILE,
    check_timeout: int = CHECK_TIMEOUT,
) -> Tuple[bool, Dict[str, int], str]:
    """Run integrity check only and return a UI-friendly summary."""
    try:
        start_time = time.time()
        parsed_tasks = repo_config.parse_repo_groups(config_file)
        if not parsed_tasks:
            raise ValueError("未找到任何仓库任务")

        total_repos = len(parsed_tasks)

        success_count, fail_count, failed_tasks = check_repos_parallel(
            parsed_tasks,
            parallel_tasks=tasks,
            timeout=check_timeout,
        )

        if failed_tasks:
            save_failed_repos(
                failed_tasks,
                failed_repos_file,
                repo_config.REPO_OWNER or "qiao-925",
            )

        result = {
            "total": total_repos,
            "success": success_count,
            "fail": fail_count,
            "duration": int(time.time() - start_time),
            "failed_file": str(failed_repos_file) if failed_tasks else "",
        }
        return True, result, ""

    except SystemExit:
        return False, {}, "配置文件解析失败"
    except Exception as e:
        return False, {}, str(e)
