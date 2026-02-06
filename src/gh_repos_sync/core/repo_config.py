"""Repository config read/write and sync operations."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..domain.repo_groups import (
    add_repos_to_unclassified,
    extract_existing_repos,
    extract_owner,
    get_group_folder as build_group_folder,
    parse_groups_and_tags,
    parse_repo_tasks,
    render_repo_groups_text,
)
from ..infra.github_api import fetch_public_repos
from ..infra.logger import log_error, log_info, log_success
from ..infra.paths import REPOS_DIR, SCRIPT_DIR

# 默认配置文件
CONFIG_FILE = "REPO-GROUPS.md"

# 最近一次解析得到的仓库所有者（供 UI 展示）
REPO_OWNER: Optional[str] = None

DEFAULT_GROUP_TAGS: Dict[str, str] = {}
DEFAULT_GROUPS: List[str] = []

OWNER_PATTERN = re.compile(r"^仓库所有者:\s*(.+)$", re.MULTILINE)


def resolve_config_path(config_file: str, base_dir: Path = SCRIPT_DIR) -> Path:
    """Resolve config path from absolute/relative input.

    Supports Windows absolute paths like ``C:\\...`` when running on
    non-Windows environments.
    """
    config_path = Path(config_file)
    if not config_path.is_absolute() and not re.match(r"^[A-Za-z]:", str(config_path)):
        return base_dir / config_path
    return config_path


def read_text_preserve_encoding(path: Path) -> Tuple[str, str, str, bool]:
    """Read text while preserving encoding/newline/trailing-newline info."""
    raw = path.read_bytes()
    encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    text = raw.decode(encoding)
    newline = "\r\n" if "\r\n" in text else "\n"
    has_trailing_newline = text.endswith("\n")
    return text, encoding, newline, has_trailing_newline


def write_text_preserve_encoding(
    path: Path,
    text: str,
    encoding: str,
    newline: str,
    has_trailing_newline: bool,
) -> None:
    """Write text and preserve newline style + trailing newline behavior."""
    if has_trailing_newline and not text.endswith(newline):
        text += newline
    with path.open("w", encoding=encoding, newline="") as handle:
        handle.write(text)


def get_group_folder(group_name: str, highland: Optional[str] = None) -> Path:
    """Build local folder path for a group."""
    return build_group_folder(REPOS_DIR, group_name, highland)


def parse_repo_groups_detail(config_file: Optional[str] = None) -> Tuple[str, List[Dict[str, str]]]:
    """Parse config and return ``(owner, tasks)``."""
    if config_file is None:
        config_file = CONFIG_FILE

    config_path = resolve_config_path(config_file)

    if not config_path.exists():
        log_error(f"配置文件不存在: {config_path}")
        raise SystemExit(1)

    if not config_path.is_file():
        log_error(f"不是有效的文件: {config_path}")
        raise SystemExit(1)

    try:
        content, _, _, _ = read_text_preserve_encoding(config_path)
    except Exception as exc:
        log_error(f"读取配置文件失败: {config_path} - {exc}")
        raise SystemExit(1)

    try:
        owner = extract_owner(content)
    except ValueError as exc:
        log_error(str(exc))
        raise SystemExit(1)

    tasks = [task.to_dict() for task in parse_repo_tasks(content, owner, REPOS_DIR)]
    return owner, tasks


def parse_repo_groups(config_file: Optional[str] = None) -> List[Dict[str, str]]:
    """Parse config and return task dictionaries."""
    global REPO_OWNER
    owner, tasks = parse_repo_groups_detail(config_file)
    REPO_OWNER = owner
    return tasks


def generate_repo_groups_text(
    owner: str,
    groups: List[str],
    assignments: Dict[str, str],
    tags: Dict[str, str],
    keep_empty: bool = True,
) -> str:
    """Render REPO-GROUPS.md content."""
    return render_repo_groups_text(owner, groups, assignments, tags, keep_empty=keep_empty)


def ensure_repo_groups_file(
    path: str,
    owner: str = "",
    groups: Optional[List[str]] = None,
    tags: Optional[Dict[str, str]] = None,
    keep_empty: bool = True,
) -> Tuple[bool, str]:
    """Create REPO-GROUPS.md when missing."""
    config_path = Path(path)
    if config_path.exists():
        if config_path.is_file():
            return True, ""
        return False, f"不是有效的文件: {config_path}"

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        safe_groups = [group for group in (groups or DEFAULT_GROUPS) if group]
        text = generate_repo_groups_text(
            owner,
            safe_groups,
            {},
            tags or {},
            keep_empty=keep_empty,
        )
        write_text_preserve_encoding(config_path, text, "utf-8", "\n", True)
    except Exception as exc:
        return False, f"创建配置文件失败: {exc}"

    return True, ""


def load_groups_from_file(path: str) -> Tuple[List[str], Dict[str, str]]:
    """Load group names and tags from REPO-GROUPS.md."""
    config_path = Path(path)
    if not config_path.exists():
        return [], {}

    try:
        content, _, _, _ = read_text_preserve_encoding(config_path)
    except Exception:
        return [], {}

    return parse_groups_and_tags(content)


def write_repo_groups(
    path: str,
    owner: str,
    groups: List[str],
    assignments: Dict[str, str],
    tags: Dict[str, str],
    keep_empty: bool = True,
) -> Tuple[bool, str]:
    """Write REPO-GROUPS.md while preserving original file style."""
    config_path = Path(path)
    if not config_path.exists():
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            text = generate_repo_groups_text(owner, groups, assignments, tags, keep_empty=keep_empty)
            write_text_preserve_encoding(config_path, text, "utf-8", "\n", True)
        except Exception as exc:
            return False, f"创建配置文件失败: {exc}"
        return True, ""

    if not config_path.is_file():
        return False, f"不是有效的文件: {config_path}"

    try:
        _, encoding, newline, has_trailing_newline = read_text_preserve_encoding(config_path)
    except Exception as exc:
        return False, f"读取配置文件失败: {exc}"

    text = generate_repo_groups_text(owner, groups, assignments, tags, keep_empty=keep_empty)
    text = text.replace("\n", newline)

    try:
        write_text_preserve_encoding(config_path, text, encoding, newline, has_trailing_newline)
    except Exception as exc:
        return False, f"写入配置文件失败: {exc}"

    return True, ""


def _fetch_public_repo_names(owner: str, token: Optional[str] = None) -> List[str]:
    success, repos, error = fetch_public_repos(owner, token=token)
    if not success:
        raise ValueError(error)

    names = [str(repo.get("name", "")).strip() for repo in repos]
    return [name for name in names if name]


def read_owner(config_file: str = CONFIG_FILE) -> Tuple[bool, str, str]:
    """Read owner from REPO-GROUPS.md without raising exceptions."""
    config_path = resolve_config_path(config_file)
    if not config_path.exists():
        return False, "", f"配置文件不存在: {config_path}"
    if not config_path.is_file():
        return False, "", f"不是有效的文件: {config_path}"

    try:
        content, _, _, _ = read_text_preserve_encoding(config_path)
    except Exception as exc:
        return False, "", f"读取配置文件失败: {exc}"

    try:
        owner = extract_owner(content)
    except ValueError as exc:
        return False, "", str(exc)
    return True, owner, ""


def write_owner(config_file: str, owner: str) -> Tuple[bool, str]:
    """Write/update owner and keep original encoding/newline style."""
    config_path = resolve_config_path(config_file)
    if not config_path.exists():
        return False, f"配置文件不存在: {config_path}"
    if not config_path.is_file():
        return False, f"不是有效的文件: {config_path}"

    try:
        content, encoding, newline, has_trailing_newline = read_text_preserve_encoding(config_path)
    except Exception as exc:
        return False, f"读取配置文件失败: {exc}"

    lines = content.splitlines()
    updated = False
    for idx, line in enumerate(lines):
        if OWNER_PATTERN.match(line):
            lines[idx] = f"仓库所有者: {owner}"
            updated = True
            break

    if not updated:
        insert_at = 0
        if lines:
            insert_at = 1
            if len(lines) > 1 and lines[1].strip() == "":
                insert_at = 2
        lines.insert(insert_at, f"仓库所有者: {owner}")
        if insert_at + 1 < len(lines) and lines[insert_at + 1].strip() != "":
            lines.insert(insert_at + 1, "")

    updated_text = newline.join(lines)
    try:
        write_text_preserve_encoding(config_path, updated_text, encoding, newline, has_trailing_newline)
    except Exception as exc:
        return False, f"写入配置文件失败: {exc}"

    return True, ""


def preview_sync(
    config_file: str = CONFIG_FILE,
    owner_override: Optional[str] = None,
    token: Optional[str] = None,
) -> Tuple[bool, str, List[str], str]:
    """Preview newly added repos from GitHub without writing file."""
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
        remote_repos = _fetch_public_repo_names(owner, token=token)
    except ValueError as exc:
        return False, owner, [], str(exc)

    new_repos = sorted([repo for repo in remote_repos if repo not in existing_repos])
    return True, owner, new_repos, ""


def apply_sync(config_file: str, new_repos: List[str]) -> Tuple[bool, str]:
    """Write newly discovered repos to `未分类` group."""
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


def sync_repos(config_file: str = CONFIG_FILE) -> int:
    """Sync newly added repos to `未分类` group."""
    config_path = resolve_config_path(config_file)
    if not config_path.exists():
        log_error(f"配置文件不存在: {config_path}")
        return 1
    if not config_path.is_file():
        log_error(f"不是有效的文件: {config_path}")
        return 1

    try:
        content, encoding, newline, has_trailing_newline = read_text_preserve_encoding(config_path)
    except Exception as exc:
        log_error(f"读取配置文件失败: {config_path} - {exc}")
        return 1

    try:
        owner = extract_owner(content)
    except ValueError as exc:
        log_error(str(exc))
        return 1

    existing_repos = set(extract_existing_repos(content))

    log_info(f"开始同步公共仓库（owner: {owner}）")
    try:
        remote_repos = _fetch_public_repo_names(owner)
    except ValueError as exc:
        log_error(str(exc))
        return 1

    new_repos = sorted([repo for repo in remote_repos if repo not in existing_repos])
    if not new_repos:
        log_info("没有新增仓库，REPO-GROUPS.md 已是最新")
        return 0

    lines = content.splitlines()
    updated_lines, added_count = add_repos_to_unclassified(lines, new_repos)
    if added_count == 0:
        log_info("未分类分组已包含新增仓库，无需更新")
        return 0

    updated_text = newline.join(updated_lines)
    try:
        write_text_preserve_encoding(config_path, updated_text, encoding, newline, has_trailing_newline)
    except Exception as exc:
        log_error(f"写入配置文件失败: {config_path} - {exc}")
        return 1

    log_success(f"同步完成，新增 {added_count} 个仓库已写入\"未分类\"")
    for repo in new_repos:
        log_info(f"+ {repo}")

    return 0


__all__ = [
    "CONFIG_FILE",
    "REPO_OWNER",
    "DEFAULT_GROUP_TAGS",
    "DEFAULT_GROUPS",
    "resolve_config_path",
    "read_text_preserve_encoding",
    "write_text_preserve_encoding",
    "get_group_folder",
    "parse_repo_groups_detail",
    "parse_repo_groups",
    "generate_repo_groups_text",
    "ensure_repo_groups_file",
    "load_groups_from_file",
    "write_repo_groups",
    "read_owner",
    "write_owner",
    "preview_sync",
    "apply_sync",
    "sync_repos",
]
