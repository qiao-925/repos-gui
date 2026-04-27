"""CloneX CLI: gist-driven, group-aware GitHub multi-repo cloner.

The CLI is intentionally tiny and opinionated. There are no flat-mode or
per-group flags; the gist is the single source of truth and the user
maintains it manually via the URL printed at the end of each run.

Pipeline (zero arguments needed):

1. Resolve the GitHub owner from the cached/explicit token.
2. Discover the user's REPO-GROUPS gist. Create a private one with a
   bootstrap template if none exists yet.
3. Append any GitHub repos missing from the gist into its ``未分类``
   group, then push the patch back. Existing manual groupings stay
   untouched.
4. Parse the gist content into per-repo tasks rooted at ``--output``.
5. Clone every repo in parallel, using the per-group folder layout
   determined by the gist (one sub-folder per group).
6. Drop a ``<group>.code-workspace`` file inside each populated group
   folder so the user can open the whole group in their IDE with one
   click.
7. Print the gist URL so the user can refine groupings before next run.
"""

from __future__ import annotations

import argparse
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional

from .application.sync_with_remote import sync_repos_to_gist_uncategorized
from .core.parallel import execute_parallel_clone
from .core.workspace import write_workspace_file
from .domain.repo_groups import parse_repo_tasks
from .infra import auth
from .infra.gist_config import gist_manager

DEFAULT_OUTPUT_DIR = Path.cwd() / "clonex-repos"
DEFAULT_PARALLEL_TASKS = 10
DEFAULT_PARALLEL_CONNECTIONS = 20
GIST_FILENAME = "REPO-GROUPS.md"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clonex",
        description="CloneX: clone all GitHub repos into per-group folders driven by a REPO-GROUPS gist.",
    )
    parser.add_argument(
        "--owner",
        default=None,
        help="GitHub owner. Defaults to the cached login from the saved token.",
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
        help="GitHub token override. If omitted, the cached token is used.",
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


def _normalize_output_path_arg(output: str) -> Path:
    raw_output = (output or "").strip()
    while raw_output and raw_output[-1] in (".", " "):
        raw_output = raw_output[:-1]
    if not raw_output:
        raw_output = str(DEFAULT_OUTPUT_DIR)
    return Path(raw_output).expanduser().resolve()


def _group_tasks_by_folder(tasks: List[Dict[str, str]]) -> "OrderedDict[str, List[Dict[str, str]]]":
    grouped: "OrderedDict[str, List[Dict[str, str]]]" = OrderedDict()
    for task in tasks:
        group_folder = task.get("group_folder") or ""
        grouped.setdefault(group_folder, []).append(task)
    return grouped


def _generate_workspaces(
    tasks: List[Dict[str, str]],
    failed_tasks: List[Dict[str, str]],
) -> int:
    """Drop one .code-workspace per group, listing successfully cloned repos."""
    failed_repo_fulls = {t.get("repo_full", "") for t in failed_tasks}
    by_folder = _group_tasks_by_folder(tasks)
    written = 0
    for group_folder, group_tasks in by_folder.items():
        if not group_folder:
            continue
        folder_path = Path(group_folder)
        if not folder_path.exists():
            continue
        repo_dirs = [
            t.get("repo_name", "")
            for t in group_tasks
            if t.get("repo_full") not in failed_repo_fulls and t.get("repo_name")
        ]
        if not repo_dirs:
            continue
        group_name = group_tasks[0].get("group_name") or folder_path.name
        ok, _ = write_workspace_file(folder_path, group_name, repo_dirs)
        if ok:
            written += 1
    return written


def _print_summary(success: int, fail: int, total: int, gist_url: str) -> int:
    print()
    print(f"finished: total={total} success={success} fail={fail}")
    if gist_url:
        print(f"edit groups at: {gist_url}")
    return 0 if fail == 0 else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    token = args.token if args.token is not None else auth.load_token()[0]

    owner = _resolve_owner(args.owner, token)
    if not owner:
        print("missing GitHub owner. pass --owner or sign in first.", file=sys.stderr)
        return 1

    # Step 1: discover or create the REPO-GROUPS gist
    ok, gist_id, gist_url, was_created, err = gist_manager.discover_or_create_repo_groups_gist(
        owner=owner,
        token=token,
        filename=GIST_FILENAME,
    )
    if not ok:
        print(f"failed to discover/create REPO-GROUPS gist: {err}", file=sys.stderr)
        return 1
    if was_created:
        print(f"created new gist: {gist_url}")

    # Step 2: append GitHub repos missing from the gist into 未分类
    ok, added, content, err = sync_repos_to_gist_uncategorized(
        owner=owner,
        gist_id=gist_id,
        token=token,
        filename=GIST_FILENAME,
    )
    if not ok:
        print(f"failed to sync repos to gist: {err}", file=sys.stderr)
        return 1
    if added > 0:
        print(f"appended {added} new repo(s) to the gist's 未分类 group.")

    # Step 3: parse gist into per-repo tasks rooted at --output
    output_dir = _normalize_output_path_arg(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    parsed_tasks = parse_repo_tasks(content, owner, output_dir)
    tasks_dicts: List[Dict[str, str]] = [t.to_dict() for t in parsed_tasks]

    print(f"owner={owner}")
    print(f"output={output_dir}")
    print(f"repos={len(tasks_dicts)}")

    if not tasks_dicts:
        print("no repos to clone (gist is empty).")
        return _print_summary(success=0, fail=0, total=0, gist_url=gist_url)

    # Step 4: clone all repos in parallel, honouring per-group folders
    success_count, fail_count, failed_tasks = execute_parallel_clone(
        tasks_dicts,
        args.tasks,
        args.connections,
        token=token,
        progress_cb=None,
    )

    # Step 5: emit one .code-workspace per group
    workspace_count = _generate_workspaces(tasks_dicts, failed_tasks)
    if workspace_count:
        print(f"generated {workspace_count} .code-workspace file(s).")

    return _print_summary(success_count, fail_count, len(tasks_dicts), gist_url)


if __name__ == "__main__":
    raise SystemExit(main())
