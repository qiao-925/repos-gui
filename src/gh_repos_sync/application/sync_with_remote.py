"""Application service: keep the REPO-GROUPS gist aligned with GitHub.

The CLI never reorganises a user's groups; instead it makes sure every
repository that exists on GitHub also exists somewhere in the gist. New
repositories are appended to the ``未分类`` section so the user can move
them into the right group manually.

Responsibilities of :func:`sync_repos_to_gist_uncategorized`:

1. Fetch the current GitHub repositories for ``owner``.
2. Download the latest gist content (forced refresh — we want truth).
3. Compute which repo names are not yet listed anywhere in the gist.
4. Append the missing names under ``未分类`` while preserving the rest
   of the file verbatim.
5. Upload the patched content back to the same gist when (and only when)
   something changed.

The function returns ``(ok, added_count, content, error)`` where
``content`` is the final gist body (post-update) so callers can parse it
without an extra round trip.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from ..domain.repo_groups import (
    add_repos_to_unclassified,
    extract_existing_repos,
)
from ..infra.gist_config import gist_manager
from ..infra.github_api import fetch_owner_repos
from ..infra.logger import log_info, log_success, log_warning


def sync_repos_to_gist_uncategorized(
    owner: str,
    gist_id: str,
    token: Optional[str] = None,
    filename: str = "REPO-GROUPS.md",
) -> Tuple[bool, int, str, str]:
    """Append GitHub repos missing from the gist into ``未分类``.

    Returns ``(ok, added_count, final_content, error)``.
    ``final_content`` is empty when ``ok`` is False.
    """

    if not owner:
        return False, 0, "", "owner is required"
    if not gist_id:
        return False, 0, "", "gist_id is required"

    # 1. Pull GitHub repos
    ok, repos, err = fetch_owner_repos(owner, token=token or None)
    if not ok:
        return False, 0, "", f"failed to fetch GitHub repos: {err}"

    github_names: List[str] = []
    for repo in repos:
        name = str(repo.get("name") or "").strip()
        if name:
            github_names.append(name)

    # 2. Pull current gist content (force refresh — we want canonical truth)
    ok, content, err = gist_manager.download_config(
        gist_id, filename, token=token, force_refresh=True
    )
    if not ok:
        return False, 0, "", f"failed to download gist: {err}"

    # 3. Diff: GitHub names not present anywhere in the gist
    existing_in_gist = set(extract_existing_repos(content))
    missing = [name for name in github_names if name not in existing_in_gist]

    if not missing:
        log_info("Gist 已包含全部 GitHub 仓库，无需追加")
        return True, 0, content, ""

    # 4. Append missing names under 未分类
    lines = content.splitlines()
    updated_lines, added = add_repos_to_unclassified(lines, missing)
    if added <= 0:
        # Could happen if the names happen to already be in 未分类 even
        # though our quick check disagreed (shouldn't, but be defensive).
        log_warning("发现 GitHub 仓库未在 Gist 中，但 add_repos_to_unclassified 报告无追加")
        return True, 0, content, ""

    new_content = "\n".join(updated_lines)
    if not new_content.endswith("\n"):
        new_content += "\n"

    # 5. Push back
    ok, err = gist_manager.upload_config(
        gist_id, new_content, filename, token=token
    )
    if not ok:
        return False, 0, "", f"failed to upload gist: {err}"

    log_success(f"已追加 {added} 个新仓库到 Gist 的『未分类』组")
    return True, added, new_content, ""


__all__ = ["sync_repos_to_gist_uncategorized"]
