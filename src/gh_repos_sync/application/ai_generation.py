"""Application service for AI-based repo group generation."""

from typing import Callable, Dict, List, Optional, Tuple

from ..core import repo_config
from ..infra import ai
from ..infra.github_api import fetch_public_repos


def generate_repo_groups_with_ai(
    owner: str,
    token: str,
    config_file: str,
    groups: List[str],
    tags: Dict[str, str],
    api_key: str,
    base_url: str,
    model: str,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Tuple[bool, int, str]:
    """Fetch repos, classify with AI, and write REPO-GROUPS.md."""
    success, repos, error = fetch_public_repos(owner, token=token or None)
    if not success:
        return False, 0, error

    mapping, error = ai.classify_repos(
        repos,
        groups,
        api_key,
        base_url=base_url,
        model=model,
        progress_cb=progress_cb,
    )
    if error:
        return False, 0, error

    assignments: Dict[str, str] = {}
    for repo in repos:
        name = str(repo.get("name", "")).strip()
        if not name:
            continue
        group = mapping.get(name, "").strip() or "未分类"
        assignments[name] = group

    groups: List[str] = sorted({group for group in assignments.values() if group})
    ok, error = repo_config.write_repo_groups(
        config_file,
        owner,
        groups,
        assignments,
        tags,
        keep_empty=True,
    )
    if not ok:
        return False, 0, error

    return True, len(repos), ""
