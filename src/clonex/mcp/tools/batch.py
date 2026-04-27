# Arbitrary-list batch execution tools (C2 group).
#
# Lets agents freely compose any repo set and fan them out in parallel. Thin
# wrappers over the existing `core/` parallel helpers; reuses the same thread
# pool semantics the GUI relies on.
#
# Tools:
#   - clone_repos_batch : parallel clone for an arbitrary task list
#   - pull_repos_batch  : parallel pull  for an arbitrary task list
#   - check_repos_batch : parallel check for an arbitrary task list (read-only)

import asyncio
from typing import Any, Callable, Dict, List, Tuple

from mcp.server.fastmcp import Context

from ...core.check import check_repos_parallel
from ...core.parallel import execute_parallel_clone
from ...core.pull import execute_parallel_pull
from ..app import mcp
from ..context import get_github_token
from ..errors import E_INVALID_ARG, err, ok


def _normalize_task(task: Dict[str, Any]) -> Dict[str, str]:
    return {
        "repo_full": str(task.get("repo_full", "")).strip(),
        "repo_name": str(task.get("repo_name", "")).strip(),
        "group_folder": str(task.get("group_folder", "")).strip(),
        "group_name": str(task.get("group_name", "")).strip(),
        "highland": str(task.get("highland", "")).strip(),
    }


def _validate_tasks(raw_tasks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, str]], str]:
    """Normalize and validate a list of task dicts.

    Returns `(normalized_tasks, error_message)`. `error_message` is empty on success.
    """
    normalized: List[Dict[str, str]] = []
    for idx, task in enumerate(raw_tasks):
        if not isinstance(task, dict):
            return [], f"tasks[{idx}] is not a dict"
        item = _normalize_task(task)
        missing = [
            key for key in ("repo_full", "repo_name", "group_folder") if not item[key]
        ]
        if missing:
            return [], f"tasks[{idx}] missing required fields: {missing}"
        normalized.append(item)
    return normalized, ""


def _make_progress_bridge(
    ctx: Context, loop: asyncio.AbstractEventLoop
) -> Callable[..., None]:
    """Build a thread-safe progress callback that forwards to MCP progress.

    The `core/*` parallel helpers all call `progress_cb(done, total, success, fail)`
    from worker threads, so we bounce through `run_coroutine_threadsafe`.
    """

    def cb(done: int, total: int, *rest: int) -> None:
        success = rest[0] if len(rest) >= 1 else 0
        fail = rest[1] if len(rest) >= 2 else 0
        message = f"{done}/{total} done (ok={success}, fail={fail})"
        try:
            future = asyncio.run_coroutine_threadsafe(
                ctx.report_progress(
                    progress=float(done),
                    total=float(total),
                    message=message,
                ),
                loop,
            )
            future.result(timeout=5)
        except Exception:
            # Progress is best-effort; never let it break the actual work.
            pass

    return cb


@mcp.tool()
async def clone_repos_batch(
    ctx: Context,
    tasks: List[Dict[str, Any]],
    parallel_tasks: int = 4,
    parallel_connections: int = 8,
    dry_run: bool = True,
) -> dict:
    """Clone an arbitrary list of repositories in parallel.

    Each task must include `repo_full`, `repo_name`, `group_folder`.
    Optional: `group_name`, `highland`.
    """
    if not tasks:
        return err(E_INVALID_ARG, "tasks is empty")

    normalized, errmsg = _validate_tasks(tasks)
    if errmsg:
        return err(E_INVALID_ARG, errmsg)

    if dry_run:
        return ok(
            {
                "dry_run": True,
                "count": len(normalized),
                "would_execute": normalized,
                "parallel_tasks": parallel_tasks,
                "parallel_connections": parallel_connections,
                "hint": "Call again with dry_run=false to actually clone",
            }
        )

    token = get_github_token()
    loop = asyncio.get_running_loop()
    progress_cb = _make_progress_bridge(ctx, loop)

    success_count, fail_count, failed_tasks = await asyncio.to_thread(
        execute_parallel_clone,
        normalized,
        parallel_tasks,
        parallel_connections,
        token,
        progress_cb,
    )

    return ok(
        {
            "dry_run": False,
            "total": len(normalized),
            "success": success_count,
            "fail": fail_count,
            "failed_tasks": failed_tasks,
        }
    )


@mcp.tool()
async def pull_repos_batch(
    ctx: Context,
    tasks: List[Dict[str, Any]],
    parallel_tasks: int = 4,
    dry_run: bool = True,
) -> dict:
    """Pull an arbitrary list of local repositories in parallel (fast-forward only)."""
    if not tasks:
        return err(E_INVALID_ARG, "tasks is empty")

    normalized, errmsg = _validate_tasks(tasks)
    if errmsg:
        return err(E_INVALID_ARG, errmsg)

    if dry_run:
        return ok(
            {
                "dry_run": True,
                "count": len(normalized),
                "would_execute": normalized,
                "parallel_tasks": parallel_tasks,
                "hint": "Call again with dry_run=false to actually pull",
            }
        )

    token = get_github_token()
    loop = asyncio.get_running_loop()
    progress_cb = _make_progress_bridge(ctx, loop)

    success_count, fail_count, failed_tasks = await asyncio.to_thread(
        execute_parallel_pull,
        normalized,
        parallel_tasks,
        token,
        progress_cb,
    )

    return ok(
        {
            "dry_run": False,
            "total": len(normalized),
            "success": success_count,
            "fail": fail_count,
            "failed_tasks": failed_tasks,
        }
    )


@mcp.tool()
async def check_repos_batch(
    ctx: Context,
    tasks: List[Dict[str, Any]],
    parallel_tasks: int = 5,
    timeout: int = 30,
) -> dict:
    """Check `git fsck` on an arbitrary list of repositories in parallel. Read-only."""
    if not tasks:
        return err(E_INVALID_ARG, "tasks is empty")

    normalized, errmsg = _validate_tasks(tasks)
    if errmsg:
        return err(E_INVALID_ARG, errmsg)

    loop = asyncio.get_running_loop()
    progress_cb = _make_progress_bridge(ctx, loop)

    success_count, fail_count, failed_tasks = await asyncio.to_thread(
        check_repos_parallel,
        normalized,
        parallel_tasks,
        timeout,
        progress_cb,
    )

    return ok(
        {
            "total": len(normalized),
            "success": success_count,
            "fail": fail_count,
            "failed_tasks": failed_tasks,
        }
    )
