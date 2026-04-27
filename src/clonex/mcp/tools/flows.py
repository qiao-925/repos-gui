# High-level workflow tools (D group).
#
# Compose multi-step operations that mirror the buttons in the GUI but are
# driven by agents. Progress is streamed via MCP `report_progress`.
#
# Tools:
#   - clone_group  : clone all repos under a given group in REPO-GROUPS.md
#   - update_all   : pull all repos listed in REPO-GROUPS.md
#   - retry_failed : re-clone the failed-repos list

import asyncio
from typing import Dict, List, Optional, Tuple

from mcp.server.fastmcp import Context

from ...core import repo_config
from ...core.failed_repos import save_failed_repos
from ...core.parallel import execute_parallel_clone
from ...core.pull import execute_parallel_pull
from ...domain.repo_groups import extract_owner, parse_repo_tasks
from ...infra.paths import REPOS_DIR
from ..app import mcp
from ..context import (
    failed_repos_path,
    get_cached_owner,
    get_github_token,
    resolve_config_path,
)
from ..errors import (
    E_CONFIG_MISSING,
    E_INTERNAL,
    E_INVALID_ARG,
    err,
    ok,
)
from .batch import _make_progress_bridge


def _parse_tasks_from_config(
    config_file: Optional[str],
) -> Tuple[Optional[List[Dict[str, str]]], str, str]:
    """Parse `REPO-GROUPS.md`-style file into task dicts.

    Returns `(tasks_or_none, owner, error_message)`. `error_message` is empty on success.
    """
    path = resolve_config_path(config_file or None)
    if not path.exists():
        return None, "", f"Config file not found: {path}"
    try:
        content, _enc, _nl, _trail = repo_config.read_text_preserve_encoding(path)
    except Exception as exc:
        return None, "", f"Read config failed: {exc}"
    try:
        owner = extract_owner(content)
    except ValueError as exc:
        return None, "", str(exc)
    tasks = [task.to_dict() for task in parse_repo_tasks(content, owner, REPOS_DIR)]
    return tasks, owner, ""


@mcp.tool()
async def clone_group(
    ctx: Context,
    group_name: str,
    config_file: str = "",
    parallel_tasks: int = 4,
    parallel_connections: int = 8,
    dry_run: bool = True,
) -> dict:
    """Clone all repos belonging to the given group defined in REPO-GROUPS.md."""
    if not group_name.strip():
        return err(E_INVALID_ARG, "group_name is required")

    tasks, owner, errmsg = _parse_tasks_from_config(config_file)
    if errmsg:
        return err(E_CONFIG_MISSING, errmsg)
    assert tasks is not None  # noqa: S101  (errmsg would have been set otherwise)

    filtered = [t for t in tasks if t.get("group_name") == group_name.strip()]
    if not filtered:
        return err(E_INVALID_ARG, f"No repos found under group: {group_name}")

    if dry_run:
        return ok(
            {
                "dry_run": True,
                "group": group_name,
                "owner": owner,
                "count": len(filtered),
                "would_execute": filtered,
                "hint": "Call again with dry_run=false to actually clone",
            }
        )

    token = get_github_token()
    loop = asyncio.get_running_loop()
    progress_cb = _make_progress_bridge(ctx, loop)

    success_count, fail_count, failed_tasks = await asyncio.to_thread(
        execute_parallel_clone,
        filtered,
        parallel_tasks,
        parallel_connections,
        token,
        progress_cb,
    )

    if failed_tasks:
        save_failed_repos(failed_tasks, failed_repos_path(), owner or "")

    return ok(
        {
            "dry_run": False,
            "group": group_name,
            "owner": owner,
            "total": len(filtered),
            "success": success_count,
            "fail": fail_count,
            "failed_tasks": failed_tasks,
        }
    )


@mcp.tool()
async def update_all(
    ctx: Context,
    config_file: str = "",
    parallel_tasks: int = 4,
    dry_run: bool = True,
) -> dict:
    """Run `git pull --ff-only` on all repos defined in REPO-GROUPS.md."""
    tasks, owner, errmsg = _parse_tasks_from_config(config_file)
    if errmsg:
        return err(E_CONFIG_MISSING, errmsg)
    assert tasks is not None  # noqa: S101

    if not tasks:
        return ok(
            {
                "dry_run": dry_run,
                "owner": owner,
                "total": 0,
                "success": 0,
                "fail": 0,
                "failed_tasks": [],
            }
        )

    if dry_run:
        return ok(
            {
                "dry_run": True,
                "owner": owner,
                "count": len(tasks),
                "hint": "Call again with dry_run=false to actually pull",
            }
        )

    token = get_github_token()
    loop = asyncio.get_running_loop()
    progress_cb = _make_progress_bridge(ctx, loop)

    success_count, fail_count, failed_tasks = await asyncio.to_thread(
        execute_parallel_pull,
        tasks,
        parallel_tasks,
        token,
        progress_cb,
    )

    if failed_tasks:
        save_failed_repos(failed_tasks, failed_repos_path(), owner or "")

    return ok(
        {
            "dry_run": False,
            "owner": owner,
            "total": len(tasks),
            "success": success_count,
            "fail": fail_count,
            "failed_tasks": failed_tasks,
        }
    )


@mcp.tool()
async def retry_failed(
    ctx: Context,
    parallel_tasks: int = 4,
    parallel_connections: int = 8,
    dry_run: bool = True,
) -> dict:
    """Re-run clone for the repos in `failed-repos.txt` (the GUI-shared failure list)."""
    path = failed_repos_path()
    if not path.exists():
        return ok(
            {
                "dry_run": dry_run,
                "path": str(path),
                "total": 0,
                "repos": [],
                "hint": "No failed-repos list found",
            }
        )

    tasks, owner, errmsg = _parse_tasks_from_config(str(path))
    if errmsg:
        return err(E_INTERNAL, errmsg)
    assert tasks is not None  # noqa: S101

    if not tasks:
        return ok({"dry_run": dry_run, "path": str(path), "total": 0, "repos": []})

    if dry_run:
        return ok(
            {
                "dry_run": True,
                "owner": owner,
                "count": len(tasks),
                "path": str(path),
                "would_execute": tasks,
                "hint": "Call again with dry_run=false to actually retry",
            }
        )

    token = get_github_token()
    loop = asyncio.get_running_loop()
    progress_cb = _make_progress_bridge(ctx, loop)

    success_count, fail_count, failed_tasks = await asyncio.to_thread(
        execute_parallel_clone,
        tasks,
        parallel_tasks,
        parallel_connections,
        token,
        progress_cb,
    )

    # Rewrite failed list with the remaining failures; empty list clears the file.
    save_failed_repos(failed_tasks, path, owner or "")

    return ok(
        {
            "dry_run": False,
            "owner": owner,
            "path": str(path),
            "total": len(tasks),
            "success": success_count,
            "fail": fail_count,
            "failed_tasks": failed_tasks,
        }
    )
