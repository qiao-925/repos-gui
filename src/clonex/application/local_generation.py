"""Application service for rule-based local repo group generation."""

from typing import Callable, Dict, List, Optional, Tuple

from ..core import repo_config
from ..infra.github_api import fetch_owner_repos


def generate_repo_groups_with_rules(
    owner: str,
    token: str,
    config_file: str,
    groups: List[str],
    tags: Dict[str, str],
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Tuple[bool, int, str]:
    """Fetch repos, classify with simple local rules (language), and write REPO-GROUPS.md."""
    success, repos, error = fetch_owner_repos(
        owner,
        token=token or None,
    )
    if not success:
        return False, 0, error

    assignments: Dict[str, str] = {}
    for idx, repo in enumerate(repos):
        name = str(repo.get("name", "")).strip()
        if not name:
            continue
        
        # 核心简化逻辑：按主要开发语言分类，如果没有则放入“未分类”
        lang = str(repo.get("language", "")).strip()
        group = lang if lang else "未分类"
        
        # 简单做一点别名优化
        if group == "Jupyter Notebook":
            group = "Python"
            
        assignments[name] = group
        
        if progress_cb:
            progress_cb(idx + 1, len(repos))

    # 合并已有分组，保证不会丢失
    final_groups: List[str] = list(groups)
    for g in assignments.values():
        if g not in final_groups:
            final_groups.append(g)

    ok, error = repo_config.write_repo_groups(
        config_file,
        owner,
        final_groups,
        assignments,
        tags,
        keep_empty=True,
    )
    if not ok:
        return False, 0, error

    return True, len(repos), ""
