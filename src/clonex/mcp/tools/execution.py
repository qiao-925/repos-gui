# Single-repo atomic execution tools (C group).
#
# Tools:
#   - clone_repo : clone one repository
#   - pull_repo  : git pull --ff-only on one local repository
#   - check_repo : git fsck on one local repository

import asyncio
from pathlib import Path

from ...core import check as check_mod
from ...core import clone as clone_mod
from ...core import pull as pull_mod
from ..app import mcp
from ..context import default_clone_root, get_github_token
from ..errors import E_GIT_EXEC, E_INVALID_ARG, err, ok


@mcp.tool()
async def clone_repo(
    owner: str,
    repo: str,
    group_folder: str = "",
    parallel_connections: int = 8,
    dry_run: bool = True,
) -> dict:
    """Clone a single repository.

    `group_folder` defaults to the GUI's default clone root.
    `dry_run=True` returns what would be executed without touching disk.
    """
    if not owner.strip() or not repo.strip():
        return err(E_INVALID_ARG, "owner and repo are required")

    repo_full = f"{owner.strip()}/{repo.strip()}"
    effective_folder = group_folder.strip() or str(default_clone_root())
    target_path = str(Path(effective_folder) / repo)

    if dry_run:
        return ok(
            {
                "dry_run": True,
                "would_execute": {
                    "repo_full": repo_full,
                    "repo_name": repo,
                    "target_path": target_path,
                    "parallel_connections": parallel_connections,
                },
                "hint": "Call again with dry_run=false to actually clone",
            }
        )

    token = get_github_token()
    success = await asyncio.to_thread(
        clone_mod.clone_repo,
        repo_full,
        repo,
        effective_folder,
        parallel_connections,
        token,
    )
    if not success:
        return err(E_GIT_EXEC, f"Clone failed: {repo_full}")

    return ok(
        {
            "dry_run": False,
            "repo_full": repo_full,
            "path": target_path,
            "cloned": True,
        }
    )


@mcp.tool()
async def pull_repo(repo_path: str, dry_run: bool = True) -> dict:
    """Run `git pull --ff-only` on a local repository path."""
    if not repo_path.strip():
        return err(E_INVALID_ARG, "repo_path is required")

    path = Path(repo_path)
    if not path.exists() or not (path / ".git").exists():
        return err(E_INVALID_ARG, f"Not a git repository: {path}")

    if dry_run:
        return ok(
            {
                "dry_run": True,
                "would_pull": str(path),
                "hint": "Call again with dry_run=false to actually pull",
            }
        )

    repo_name = path.name
    group_folder = str(path.parent)
    # `pull_repo` uses repo_full only for logs; the local path drives everything.
    repo_full = repo_name

    token = get_github_token()
    success, reason = await asyncio.to_thread(
        pull_mod.pull_repo,
        repo_full,
        repo_name,
        group_folder,
        token,
    )
    if not success:
        return err(E_GIT_EXEC, f"Pull failed: {reason or 'unknown'}")

    return ok({"dry_run": False, "path": str(path), "updated": True})


@mcp.tool()
async def check_repo(
    repo_path: str,
    expected_repo_full: str = "",
    timeout: int = 30,
) -> dict:
    """Run `git fsck --strict` on a local repository path. Read-only, no dry_run."""
    if not repo_path.strip():
        return err(E_INVALID_ARG, "repo_path is required")

    path = Path(repo_path)
    if not path.exists():
        return err(E_INVALID_ARG, f"Path does not exist: {path}")

    label = expected_repo_full or path.name
    valid, error_msg = await asyncio.to_thread(
        check_mod.check_repo,
        path,
        label,
        timeout,
    )
    return ok({"path": str(path), "valid": valid, "error": error_msg or ""})
