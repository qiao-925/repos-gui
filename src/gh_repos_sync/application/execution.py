"""Application services for clone/check/pull execution flows."""

import time
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from ..core import repo_config
from ..core.check import check_repos_parallel
from ..core.failed_repos import save_failed_repos
from ..core.parallel import execute_parallel_clone
from ..core.process_control import clear_shutdown_request
from ..core.pull import execute_parallel_pull

CHECK_TIMEOUT = 30
FAILED_REPOS_FILE: Path = repo_config.SCRIPT_DIR / "failed-repos.txt"
ProgressCallback = Callable[[str, int, int, int, int], None]


def run_clone_and_check(
    config_file: str,
    tasks: int,
    connections: int,
    failed_repos_file: Path = FAILED_REPOS_FILE,
    check_timeout: int = CHECK_TIMEOUT,
    progress_cb: Optional[ProgressCallback] = None,
) -> Tuple[bool, Dict[str, int], str]:
    """Run clone then integrity check, returning a UI-friendly summary."""
    try:
        clear_shutdown_request()
        start_time = time.time()
        parsed_tasks = repo_config.parse_repo_groups(config_file)
        if not parsed_tasks:
            raise ValueError("No repository tasks found in config")

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
            progress_cb=(
                lambda done, total, success, fail: progress_cb("clone", done, total, success, fail)
                if progress_cb
                else None
            ),
        )

        if success_count > 0:
            successful_tasks = [task for task in parsed_tasks if task not in failed_tasks]
            _, _, check_failed_tasks = check_repos_parallel(
                successful_tasks,
                parallel_tasks=tasks,
                timeout=check_timeout,
                progress_cb=(
                    lambda done, total, success, fail: progress_cb("check", done, total, success, fail)
                    if progress_cb
                    else None
                ),
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
        return False, {}, "Config parse failed"
    except Exception as exc:
        return False, {}, str(exc)


def run_pull_updates(
    config_file: str,
    tasks: int,
    failed_repos_file: Path = FAILED_REPOS_FILE,
    progress_cb: Optional[ProgressCallback] = None,
) -> Tuple[bool, Dict[str, int], str]:
    """Run git pull on existing local repos and return a UI-friendly summary."""
    try:
        clear_shutdown_request()
        start_time = time.time()
        parsed_tasks = repo_config.parse_repo_groups(config_file)
        if not parsed_tasks:
            raise ValueError("No repository tasks found in config")

        total_repos = len(parsed_tasks)

        if failed_repos_file.exists():
            try:
                failed_repos_file.unlink()
            except Exception:
                pass

        success_count, fail_count, failed_tasks = execute_parallel_pull(
            parsed_tasks,
            parallel_tasks=tasks,
            progress_cb=(
                lambda done, total, success, fail: progress_cb("pull", done, total, success, fail)
                if progress_cb
                else None
            ),
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
            "failed_reasons": {
                str(task.get("repo_full", "")): str(task.get("reason", "unknown"))
                for task in failed_tasks
                if task.get("repo_full")
            },
        }
        return True, result, ""

    except SystemExit:
        return False, {}, "Config parse failed"
    except Exception as exc:
        return False, {}, str(exc)
