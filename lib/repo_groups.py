# REPO-GROUPS.md 读写与分组生成

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from lib.sync import _read_text_preserve_encoding, _write_text_preserve_encoding


GROUP_HEADER_PATTERN = re.compile(r'^##\s+(.+?)(?:\s*<!--\s*(.+?)\s*-->)?\s*$')

DEFAULT_GROUP_TAGS: Dict[str, str] = {}
DEFAULT_GROUPS: List[str] = []


def ensure_repo_groups_file(
    path: str,
    owner: str = "",
    groups: Optional[List[str]] = None,
    tags: Optional[Dict[str, str]] = None,
    keep_empty: bool = True
) -> Tuple[bool, str]:嗯
    config_path = Path(path)
    if config_path.exists():
        if config_path.is_file():
            return True, ""
        return False, f"不是有效的文件: {config_path}"

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        safe_groups = [g for g in (groups or DEFAULT_GROUPS) if g]
        if not safe_groups:
            safe_groups = []
        text = generate_repo_groups_text(
            owner,
            safe_groups,
            {},
            tags or {},
            keep_empty=keep_empty
        )
        _write_text_preserve_encoding(config_path, text, "utf-8", "\n", True)
    except Exception as e:
        return False, f"创建配置文件失败: {e}"

    return True, ""


def load_groups_from_file(path: str) -> Tuple[List[str], Dict[str, str]]:
    config_path = Path(path)
    if not config_path.exists():
        return [], {}

    try:
        content, _, _, _ = _read_text_preserve_encoding(config_path)
    except Exception:
        return [], {}

    groups: List[str] = []
    tags: Dict[str, str] = {}

    for line in content.splitlines():
        match = GROUP_HEADER_PATTERN.match(line)
        if not match:
            continue
        group_name = match.group(1).strip()
        tag = (match.group(2) or "").strip()
        if group_name and group_name not in groups:
            groups.append(group_name)
        if group_name and tag:
            tags[group_name] = tag

    return groups, tags


def generate_repo_groups_text(
    owner: str,
    groups: List[str],
    assignments: Dict[str, str],
    tags: Dict[str, str],
    keep_empty: bool = True
) -> str:
    lines = [
        "# GitHub 仓库分组",
        "",
        f"仓库所有者: {owner}",
        "",
    ]

    for group in groups:
        repos = sorted([name for name, g in assignments.items() if g == group])
        if not repos and not keep_empty:
            continue
        tag = tags.get(group, "")
        if tag:
            lines.append(f"## {group} <!-- {tag} -->")
        else:
            lines.append(f"## {group}")
        for repo in repos:
            lines.append(f"- {repo}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_repo_groups(
    path: str,
    owner: str,
    groups: List[str],
    assignments: Dict[str, str],
    tags: Dict[str, str],
    keep_empty: bool = True
) -> Tuple[bool, str]:
    config_path = Path(path)
    if not config_path.exists():
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            text = generate_repo_groups_text(owner, groups, assignments, tags, keep_empty=keep_empty)
            _write_text_preserve_encoding(config_path, text, "utf-8", "\n", True)
        except Exception as e:
            return False, f"创建配置文件失败: {e}"
        return True, ""
    if not config_path.is_file():
        return False, f"不是有效的文件: {config_path}"

    try:
        _, encoding, newline, has_trailing_newline = _read_text_preserve_encoding(config_path)
    except Exception as e:
        return False, f"读取配置文件失败: {e}"

    text = generate_repo_groups_text(owner, groups, assignments, tags, keep_empty=keep_empty)
    text = text.replace("\n", newline)

    try:
        _write_text_preserve_encoding(config_path, text, encoding, newline, has_trailing_newline)
    except Exception as e:
        return False, f"写入配置文件失败: {e}"

    return True, ""
