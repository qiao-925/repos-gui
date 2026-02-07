"""Batch git pull operations for existing local repositories."""

import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .process_control import is_shutdown_requested, start_tracked_process, terminate_process, untrack_process
from ..infra.logger import log_error, log_info, log_success, log_warning


def _extract_pull_failure_reason(stderr_text: str) -> str:
    """Map common git pull stderr to concise reason tags."""
    text = (stderr_text or "").lower()
    if not text:
        return "unknown"
    if "not a git repository" in text:
        return "not_git_repo"
    if "couldn't find remote ref" in text or "no such remote" in text:
        return "remote_ref_missing"
    if "your local changes" in text or "would be overwritten" in text:
        return "local_changes_conflict"
    if "fatal: refusing to merge unrelated histories" in text:
        return "unrelated_histories"
    if "not possible to fast-forward" in text or "cannot fast-forward" in text:
        return "not_fast_forward"
    if "could not resolve host" in text or "failed to connect" in text or "timed out" in text:
        return "network_error"
    if "authentication failed" in text or "permission denied" in text:
        return "auth_error"
    return "unknown"


def pull_repo(repo_full: str, repo_name: str, group_folder: str) -> Tuple[bool, str]:
    """Run `git pull --ff-only` for one local repository."""
    if not repo_full or not repo_name or not group_folder:
        log_error("pull_repo: missing required arguments")
        return False, "invalid_arguments"

    if is_shutdown_requested():
        log_warning(f"update canceled (app is closing): {repo_full}")
        return False, "canceled"

    repo_path = Path(group_folder) / repo_name
    git_dir = repo_path / ".git"
    if not repo_path.exists() or not git_dir.exists():
        log_error(f"local repository missing, skip update: {repo_full} ({repo_path})")
        return False, "local_repo_missing"

    command = [
        "git",
        "-C",
        str(repo_path),
        "pull",
        "--ff-only",
        "--no-rebase",
        "--no-stat",
        "--no-progress",
    ]

    try:
        process = start_tracked_process(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            _, stderr_text = process.communicate()
            result_code = process.returncode
        finally:
            untrack_process(process)

        if is_shutdown_requested():
            terminate_process(process)
            log_warning(f"update canceled (app is closing): {repo_full}")
            return False, "canceled"

        if result_code != 0:
            reason = _extract_pull_failure_reason(stderr_text)
            log_error(f"update failed [{reason}]: {repo_full}")
            return False, reason

        log_success(f"update success: {repo_full}")
        return True, ""

    except Exception as exc:
        log_error(f"update exception: {repo_full} - {exc}")
        return False, "exception"


def execute_parallel_pull(
    tasks: List[Dict[str, str]],
    parallel_tasks: int,
    progress_cb: Optional[Callable[[int, int, int, int], None]] = None,
) -> Tuple[int, int, List[Dict[str, str]]]:
    """Run pull tasks in parallel and collect summary stats."""
    total = len(tasks)
    if total == 0:
        log_warning("no repositories to update")
        return 0, 0, []

    log_info(f"start batch update, total: {total}")
    log_info(f"parallel tasks: {parallel_tasks}")

    success_count = 0
    fail_count = 0
    failed_tasks: List[Dict[str, str]] = []

    if progress_cb:
        progress_cb(0, total, success_count, fail_count)

    with ThreadPoolExecutor(max_workers=parallel_tasks) as executor:
        future_to_task = {
            executor.submit(
                pull_repo,
                task["repo_full"],
                task["repo_name"],
                task["group_folder"],
            ): task
            for task in tasks
        }

        for future in as_completed(future_to_task):
            if is_shutdown_requested():
                log_warning("shutdown requested, stop collecting remaining update tasks")
                break

            task = future_to_task[future]
            try:
                success, reason = future.result()
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    task_with_reason = dict(task)
                    task_with_reason["reason"] = reason
                    failed_tasks.append(task_with_reason)
            except Exception as exc:
                fail_count += 1
                task_with_reason = dict(task)
                task_with_reason["reason"] = "exception"
                failed_tasks.append(task_with_reason)
                log_error(f"update exception: {task['repo_full']} - {exc}")

            if progress_cb:
                done = success_count + fail_count
                progress_cb(done, total, success_count, fail_count)

    log_info(f"batch update finished, success: {success_count}, fail: {fail_count}")
    return success_count, fail_count, failed_tasks

