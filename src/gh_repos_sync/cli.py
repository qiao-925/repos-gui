"""Minimal command-line entrypoint for CloneX.

This CLI depends on GitHub authorization. The first run must have a valid
cached token (or an explicit token) so it can resolve the GitHub owner,
fetch the repository list, and clone everything into one output directory
without any classification or configuration-file workflow.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from .core.parallel import execute_parallel_clone
from .infra import auth
from .infra.github_api import fetch_owner_repos

DEFAULT_OUTPUT_DIR = Path.cwd() / "clonex-repos"
DEFAULT_PARALLEL_TASKS = 10
DEFAULT_PARALLEL_CONNECTIONS = 20


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clonex",
        description="CloneX flat-list command runner.",
    )
    parser.add_argument(
        "--owner",
        default=None,
        help="GitHub owner to sync. If omitted, the cached login from the saved token is used.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory for cloned repositories (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--tasks",
        type=int,
        default=DEFAULT_PARALLEL_TASKS,
        help=f"Parallel repository tasks (default: {DEFAULT_PARALLEL_TASKS})",
    )
    parser.add_argument(
        "--connections",
        type=int,
        default=DEFAULT_PARALLEL_CONNECTIONS,
        help=f"Parallel git connections per clone (default: {DEFAULT_PARALLEL_CONNECTIONS})",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="GitHub token override. If omitted, the app uses its cached token when available.",
    )
    return parser


def _resolve_owner(owner: Optional[str], token: Optional[str]) -> str:
    normalized_owner = (owner or "").strip()
    if normalized_owner:
        return normalized_owner

    cached_login = auth.load_cached_login()
    if cached_login:
        return cached_login

    if token:
        login, _, _ = auth.fetch_user_profile(token)
        if login:
            return login

    return ""


def _print_result(success: int, fail: int, total: int) -> int:
    print(f"finished: total={total} success={success} fail={fail}")
    return 0 if fail == 0 else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    token = args.token if args.token is not None else auth.load_token()[0]
    owner = _resolve_owner(args.owner, token)
    if not owner:
        print("missing GitHub owner. pass --owner or sign in first.", file=sys.stderr)
        return 1

    success, repos, error = fetch_owner_repos(owner, token=token)
    if not success:
        print(f"failed to fetch repository list: {error}", file=sys.stderr)
        return 1

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"owner={owner}")
    print(f"output={output_dir}")
    print(f"repos={len(repos)}")

    tasks = []
    invalid_repo_count = 0
    for repo in repos:
        repo_name = str(repo.get("name") or "").strip()
        repo_full = f"{owner}/{repo_name}" if repo_name else ""
        if not repo_name:
            invalid_repo_count += 1
            continue
        tasks.append(
            {
                "repo_full": repo_full,
                "repo_name": repo_name,
                "group_folder": str(output_dir),
                "group_name": owner,
            }
        )

    success_count, fail_count, _ = execute_parallel_clone(
        tasks=tasks,
        parallel_tasks=args.tasks,
        parallel_connections=args.connections,
        token=token,
    )
    fail_count += invalid_repo_count

    return _print_result(success_count, fail_count, len(repos))


if __name__ == "__main__":
    raise SystemExit(main())
