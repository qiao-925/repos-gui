"""REPO-GROUPS.md file IO + Gist helpers (core layer).

Scope:
- File IO with encoding/newline preservation.
- Config-path resolution (relative to ``SCRIPT_DIR``).
- Parsing entry points that delegate to ``domain.repo_groups``.
- Gist push/pull helpers (to be extracted in a future Gist refactor).

Multi-step sync (preview/apply) has moved to ``application/repo_sync``;
pure parsing and rendering live in ``domain/repo_groups``.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..domain.repo_groups import (
    OWNER_PATTERN,
    extract_owner,
    parse_groups_and_tags,
    parse_repo_tasks,
    render_repo_groups_text,
)
from ..infra.gist_config import gist_manager
from ..infra.logger import log_error, log_info, log_success, log_warning
from ..infra.paths import REPOS_DIR, SCRIPT_DIR

# 默认配置文件
CONFIG_FILE = "REPO-GROUPS.md"

# 最近一次解析得到的仓库所有者（供 UI 展示）
REPO_OWNER: Optional[str] = None


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
        safe_groups = [group for group in (groups or []) if group]
        text = render_repo_groups_text(
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
            text = render_repo_groups_text(owner, groups, assignments, tags, keep_empty=keep_empty)
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

    text = render_repo_groups_text(owner, groups, assignments, tags, keep_empty=keep_empty)
    text = text.replace("\n", newline)

    try:
        write_text_preserve_encoding(config_path, text, encoding, newline, has_trailing_newline)
    except Exception as exc:
        return False, f"写入配置文件失败: {exc}"

    return True, ""


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


def load_config_from_gist(gist_id: str, filename: str = "REPO-GROUPS.md", 
                         token: Optional[str] = None, force_refresh: bool = False) -> Tuple[bool, str, str]:
    """Load configuration from GitHub Gist."""
    success, content, error = gist_manager.download_config(gist_id, filename, token, force_refresh)
    if not success:
        return False, "", error
    
    # 验证配置内容
    try:
        extract_owner(content)
        parse_groups_and_tags(content)
    except ValueError as e:
        return False, "", f"Gist 配置格式错误: {e}"
    
    return True, content, ""


def save_config_to_gist(config_file: str, gist_id: str, filename: str = "REPO-GROUPS.md",
                       token: Optional[str] = None, description: Optional[str] = None) -> Tuple[bool, str]:
    """Save local configuration to GitHub Gist."""
    config_path = resolve_config_path(config_file)
    if not config_path.exists():
        return False, f"本地配置文件不存在: {config_path}"
    
    try:
        content, _, _, _ = read_text_preserve_encoding(config_path)
    except Exception as exc:
        return False, f"读取本地配置失败: {exc}"
    
    return gist_manager.upload_config(gist_id, content, filename, token, description)


def create_gist_from_config(config_file: str, filename: str = "REPO-GROUPS.md",
                           token: Optional[str] = None, description: Optional[str] = None,
                           public: bool = False) -> Tuple[bool, str, str]:
    """Create a new Gist from local configuration."""
    config_path = resolve_config_path(config_file)
    if not config_path.exists():
        return False, "", f"本地配置文件不存在: {config_path}"
    
    try:
        content, _, _, _ = read_text_preserve_encoding(config_path)
    except Exception as exc:
        return False, "", f"读取本地配置失败: {exc}"
    
    return gist_manager.create_gist(content, filename, token, description, public)


def sync_config_from_gist(config_file: str, gist_id: str, filename: str = "REPO-GROUPS.md",
                         token: Optional[str] = None, backup: bool = True) -> Tuple[bool, str]:
    """Sync configuration from Gist to local file."""
    # 备份本地文件
    config_path = resolve_config_path(config_file)
    if backup and config_path.exists():
        backup_path = config_path.with_suffix(f"{config_path.suffix}.backup")
        try:
            import shutil
            shutil.copy2(config_path, backup_path)
            log_info(f"已备份本地配置到: {backup_path}")
        except Exception as e:
            log_warning(f"备份本地配置失败: {e}")
    
    # 从 Gist 下载
    success, content, error = load_config_from_gist(gist_id, filename, token)
    if not success:
        return False, error
    
    # 写入本地文件
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        write_text_preserve_encoding(config_path, content, "utf-8", "\n", True)
    except Exception as exc:
        return False, f"写入本地配置失败: {exc}"
    
    log_success(f"已从 Gist 同步配置到: {config_path}")
    return True, ""


def get_gist_cache_info() -> Dict[str, Dict]:
    """Get cached Gist configurations information."""
    return gist_manager.get_cached_configs()


def clear_gist_cache(gist_id: Optional[str] = None, filename: Optional[str] = None) -> None:
    """Clear Gist cache."""
    gist_manager.clear_cache(gist_id, filename)


__all__ = [
    "CONFIG_FILE",
    "REPO_OWNER",
    "resolve_config_path",
    "read_text_preserve_encoding",
    "write_text_preserve_encoding",
    "parse_repo_groups_detail",
    "parse_repo_groups",
    "ensure_repo_groups_file",
    "load_groups_from_file",
    "write_repo_groups",
    "read_owner",
    "write_owner",
    "load_config_from_gist",
    "save_config_to_gist",
    "create_gist_from_config",
    "sync_config_from_gist",
    "get_gist_cache_info",
    "clear_gist_cache",
]
