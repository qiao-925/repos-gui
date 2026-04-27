"""Application services for clone/check/pull execution flows."""

import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple, TypedDict

from ..core import repo_config
from ..core.check import check_repos_parallel
from ..core.failed_repos import save_failed_repos
from ..core.parallel import execute_parallel_clone
from ..core.process_control import clear_shutdown_request
from ..core.pull import execute_parallel_pull
from ..infra.logger import log_exception

CHECK_TIMEOUT = 30
FAILED_REPOS_FILE: Path = repo_config.SCRIPT_DIR / "failed-repos.txt"
RepoTask = Dict[str, str]
ProgressCallback = Callable[[str, int, int, int, int], None]


class ExecutionResult(TypedDict, total=False):
    total: int
    success: int
    fail: int
    duration: int
    failed_file: str
    failed_reasons: Dict[str, str]


def _load_repo_tasks(config_file: str) -> List[RepoTask]:
    parsed_tasks = repo_config.parse_repo_groups(config_file)
    if not parsed_tasks:
        raise ValueError("No repository tasks found in config")
    return parsed_tasks


def _reset_failed_repos_file(failed_repos_file: Path) -> None:
    if not failed_repos_file.exists():
        return

    try:
        failed_repos_file.unlink()
    except Exception:
        pass


def _phase_progress_callback(
    progress_cb: Optional[ProgressCallback],
    phase: str,
) -> Optional[Callable[[int, int, int, int], None]]:
    if progress_cb is None:
        return None

    return lambda done, total, success, fail: progress_cb(phase, done, total, success, fail)


def _successful_tasks(
    parsed_tasks: Sequence[RepoTask],
    failed_tasks: Sequence[RepoTask],
) -> List[RepoTask]:
    failed_repo_fulls = {
        task.get("repo_full", "")
        for task in failed_tasks
        if task.get("repo_full")
    }
    return [task for task in parsed_tasks if task.get("repo_full", "") not in failed_repo_fulls]


def _save_failed_repos_if_needed(
    failed_tasks: Sequence[RepoTask],
    failed_repos_file: Path,
) -> str:
    if not failed_tasks:
        return ""

    save_failed_repos(
        list(failed_tasks),
        failed_repos_file,
        repo_config.REPO_OWNER or "qiao-925",
    )
    return str(failed_repos_file)


def _build_execution_result(
    total_repos: int,
    start_time: float,
    failed_file: str,
    success_count: int,
    fail_count: int,
    failed_reasons: Optional[Dict[str, str]] = None,
) -> ExecutionResult:
    result: ExecutionResult = {
        "total": total_repos,
        "success": success_count,
        "fail": fail_count,
        "duration": int(time.time() - start_time),
        "failed_file": failed_file,
    }
    if failed_reasons:
        result["failed_reasons"] = failed_reasons
    return result


def run_clone_and_check(
    config_file: str,
    tasks: int,
    connections: int,
    token: Optional[str] = None,
    failed_repos_file: Path = FAILED_REPOS_FILE,
    check_timeout: int = CHECK_TIMEOUT,
    progress_cb: Optional[ProgressCallback] = None,
) -> Tuple[bool, ExecutionResult, str]:
    """Run clone then integrity check, returning a UI-friendly summary."""
    try:
        clear_shutdown_request()
        start_time = time.time()
        parsed_tasks = _load_repo_tasks(config_file)
        total_repos = len(parsed_tasks)
        _reset_failed_repos_file(failed_repos_file)

        success_count, fail_count, failed_tasks = execute_parallel_clone(
            parsed_tasks,
            tasks,
            connections,
            token=token,
            progress_cb=_phase_progress_callback(progress_cb, "clone"),
        )

        if success_count > 0:
            successful_tasks = _successful_tasks(parsed_tasks, failed_tasks)
            _, _, check_failed_tasks = check_repos_parallel(
                successful_tasks,
                parallel_tasks=tasks,
                timeout=check_timeout,
                progress_cb=_phase_progress_callback(progress_cb, "check"),
            )

            if check_failed_tasks:
                failed_tasks.extend(check_failed_tasks)
                fail_count += len(check_failed_tasks)
                success_count -= len(check_failed_tasks)

        failed_file = _save_failed_repos_if_needed(failed_tasks, failed_repos_file)
        result = _build_execution_result(
            total_repos=total_repos,
            start_time=start_time,
            failed_file=failed_file,
            success_count=success_count,
            fail_count=fail_count,
        )
        return True, result, ""

    except SystemExit:
        return False, {}, "Config parse failed"
    except Exception as exc:
        log_exception("克隆/检查流程执行失败", exc)
        return False, {}, str(exc)


def run_pull_updates(
    config_file: str,
    tasks: int,
    token: Optional[str] = None,
    failed_repos_file: Path = FAILED_REPOS_FILE,
    progress_cb: Optional[ProgressCallback] = None,
) -> Tuple[bool, ExecutionResult, str]:
    """Run git pull on existing local repos and return a UI-friendly summary."""
    try:
        clear_shutdown_request()
        start_time = time.time()
        parsed_tasks = _load_repo_tasks(config_file)
        total_repos = len(parsed_tasks)
        _reset_failed_repos_file(failed_repos_file)

        success_count, fail_count, failed_tasks = execute_parallel_pull(
            parsed_tasks,
            parallel_tasks=tasks,
            token=token,
            progress_cb=_phase_progress_callback(progress_cb, "pull"),
        )

        failed_file = _save_failed_repos_if_needed(failed_tasks, failed_repos_file)
        failed_reasons = {
            str(task.get("repo_full", "")): str(task.get("reason", "unknown"))
            for task in failed_tasks
            if task.get("repo_full")
        }
        result = _build_execution_result(
            total_repos=total_repos,
            start_time=start_time,
            failed_file=failed_file,
            success_count=success_count,
            fail_count=fail_count,
            failed_reasons=failed_reasons,
        )
        return True, result, ""

    except SystemExit:
        return False, {}, "Config parse failed"
    except Exception as exc:
        log_exception("批量更新流程执行失败", exc)
        return False, {}, str(exc)
