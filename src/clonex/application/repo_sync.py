"""Sync REPO-GROUPS.md against GitHub (preview + apply).

This is a two-step use case: `preview_sync` asks GitHub for the owner's
latest repos and returns the diff without touching disk; `apply_sync` then
writes the newly discovered repos into the `未分类` group.

Moved out of `core/repo_config` so that multi-step orchestration lives in
the application layer, per the project dependency direction
(`ui / mcp -> application -> core / domain -> infra`).
"""

from typing import List, Optional, Tuple

from ..core.repo_config import (
    CONFIG_FILE,
    read_text_preserve_encoding,
    resolve_config_path,
    write_text_preserve_encoding,
)
from ..domain.repo_groups import (
    add_repos_to_unclassified,
    extract_existing_repos,
    extract_owner,
)
from ..infra.github_api import fetch_owner_repos


def _fetch_repo_names(
    owner: str,
    token: Optional[str] = None,
) -> List[str]:
    """Fetch GitHub repo names for ``owner``; raise ``ValueError`` on failure."""
    success, repos, error = fetch_owner_repos(owner, token=token)
    if not success:
        raise ValueError(error)

    names = [str(repo.get("name", "")).strip() for repo in repos]
    return [name for name in names if name]


def preview_sync(
    config_file: str = CONFIG_FILE,
    owner_override: Optional[str] = None,
    token: Optional[str] = None,
) -> Tuple[bool, str, List[str], str]:
    """Preview newly added repos from GitHub without writing file.

    Returns ``(success, owner, new_repos, error_message)``.
    """
    config_path = resolve_config_path(config_file)
    if not config_path.exists():
        return False, "", [], f"配置文件不存在: {config_path}"
    if not config_path.is_file():
        return False, "", [], f"不是有效的文件: {config_path}"

    try:
        content, _, _, _ = read_text_preserve_encoding(config_path)
    except Exception as exc:
        return False, "", [], f"读取配置文件失败: {exc}"

    owner = owner_override.strip() if owner_override else ""
    if not owner:
        try:
            owner = extract_owner(content)
        except ValueError as exc:
            return False, "", [], str(exc)

    if not owner:
        return False, "", [], "仓库所有者信息为空"

    existing_repos = set(extract_existing_repos(content))

    try:
        remote_repos = _fetch_repo_names(owner, token=token)
    except ValueError as exc:
        return False, owner, [], str(exc)

    new_repos = sorted([repo for repo in remote_repos if repo not in existing_repos])
    return True, owner, new_repos, ""


def apply_sync(config_file: str, new_repos: List[str]) -> Tuple[bool, str]:
    """Write newly discovered repos into the ``未分类`` group."""
    config_path = resolve_config_path(config_file)
    if not config_path.exists():
        return False, f"配置文件不存在: {config_path}"

    try:
        content, encoding, newline, has_trailing_newline = read_text_preserve_encoding(config_path)
    except Exception as exc:
        return False, f"读取配置文件失败: {exc}"

    lines = content.splitlines()
    updated_lines, added_count = add_repos_to_unclassified(lines, new_repos)
    if added_count == 0:
        return True, ""

    updated_text = newline.join(updated_lines)
    try:
        write_text_preserve_encoding(config_path, updated_text, encoding, newline, has_trailing_newline)
    except Exception as exc:
        return False, f"写入配置文件失败: {exc}"

    return True, ""
