"""REPO-GROUPS.md parsing and rendering in the domain layer."""

import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .models import RepoTask


OWNER_PATTERN = re.compile(r"^仓库所有者:\s*(.+)$", re.MULTILINE)
GROUP_HEADER_PATTERN = re.compile(r"^##\s+(.+?)(?:\s*<!--\s*(.+?)\s*-->)?\s*$")
REPO_LINE_PATTERN = re.compile(r"^\s*-\s+(\S+)", re.MULTILINE)


def extract_owner(content: str) -> str:
    """Extract repository owner from markdown content."""
    match = OWNER_PATTERN.search(content)
    if not match:
        raise ValueError("未找到仓库所有者信息")

    owner = match.group(1).strip()
    if not owner:
        raise ValueError("仓库所有者信息为空")
    return owner


def extract_existing_repos(content: str) -> List[str]:
    """Extract all repo names from markdown bullet lines."""
    repos: List[str] = []
    for match in REPO_LINE_PATTERN.finditer(content):
        repo_name = match.group(1).strip()
        if repo_name:
            repos.append(repo_name)
    return repos


def parse_groups_and_tags(content: str) -> Tuple[List[str], Dict[str, str]]:
    """Extract group names and optional tags from markdown content."""
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


def get_group_folder(base_repos_dir: Path, group_name: str, highland: Optional[str] = None) -> Path:
    """Build local folder path for a group."""
    if highland:
        return base_repos_dir / f"{group_name} ({highland})"
    return base_repos_dir / group_name


def parse_repo_tasks(content: str, owner: str, base_repos_dir: Path) -> List[RepoTask]:
    """Parse markdown content into executable repo tasks."""
    tasks: List[RepoTask] = []
    current_group: Optional[str] = None
    current_highland: Optional[str] = None

    for line in content.splitlines():
        group_match = GROUP_HEADER_PATTERN.match(line)
        if group_match:
            current_group = group_match.group(1).strip()
            current_highland = (group_match.group(2) or "").strip()
            continue

        repo_match = REPO_LINE_PATTERN.match(line)
        if repo_match and current_group:
            repo_name = repo_match.group(1).strip()
            repo_full = f"{owner}/{repo_name}"
            group_folder = get_group_folder(base_repos_dir, current_group, current_highland)
            tasks.append(
                RepoTask(
                    repo_full=repo_full,
                    repo_name=repo_name,
                    group_folder=str(group_folder),
                    group_name=current_group,
                    highland=current_highland or "",
                )
            )

    return tasks


def render_repo_groups_text(
    owner: str,
    groups: Sequence[str],
    assignments: Dict[str, str],
    tags: Dict[str, str],
    keep_empty: bool = True,
) -> str:
    """Render REPO-GROUPS.md text."""
    lines = ["# GitHub 仓库分组", "", f"仓库所有者: {owner}", ""]

    for group in groups:
        repos = sorted([name for name, assigned in assignments.items() if assigned == group])
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


def add_repos_to_unclassified(lines: List[str], new_repos: List[str]) -> Tuple[List[str], int]:
    """Insert new repos into the `未分类` group and return added count."""
    if not new_repos:
        return lines, 0

    group_indices: List[Tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = GROUP_HEADER_PATTERN.match(line)
        if match:
            group_indices.append((index, match.group(1).strip()))

    sections: List[Tuple[int, int, str]] = []
    unclassified_section: Optional[Tuple[int, int, str]] = None
    for i, (start, group_name) in enumerate(group_indices):
        end = group_indices[i + 1][0] if i + 1 < len(group_indices) else len(lines)
        section = (start, end, group_name)
        sections.append(section)
        if group_name == "未分类":
            unclassified_section = section

    if unclassified_section is None:
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append("## 未分类 <!-- 未分类 -->")
        for repo in new_repos:
            lines.append(f"- {repo}")
        return lines, len(new_repos)

    start, end, _ = unclassified_section
    existing_in_section = set()
    for line in lines[start + 1 : end]:
        match = REPO_LINE_PATTERN.match(line)
        if match:
            existing_in_section.add(match.group(1).strip())

    to_add = [repo for repo in new_repos if repo not in existing_in_section]
    if not to_add:
        return lines, 0

    insert_at = end
    while insert_at > start + 1 and lines[insert_at - 1].strip() == "":
        insert_at -= 1

    for offset, repo in enumerate(to_add):
        lines.insert(insert_at + offset, f"- {repo}")

    return lines, len(to_add)


def build_failed_repo_groups_text(failed_tasks: Sequence[RepoTask], repo_owner: str) -> str:
    """Build REPO-GROUPS.md text for failed tasks retry."""
    group_repos: Dict[str, List[str]] = defaultdict(list)
    group_highlands: Dict[str, str] = {}

    for task in failed_tasks:
        group_repos[task.group_name].append(task.repo_name)
        if task.group_name not in group_highlands:
            group_highlands[task.group_name] = task.highland

    lines = ["# GitHub 仓库分组", "", f"仓库所有者: {repo_owner}", ""]
    for group_name in sorted(group_repos.keys()):
        highland = group_highlands.get(group_name, "")
        if highland:
            lines.append(f"## {group_name} <!-- {highland} -->")
        else:
            lines.append(f"## {group_name}")

        for repo in group_repos[group_name]:
            if repo:
                lines.append(f"- {repo}")
        lines.append("")

    return "\n".join(lines)


__all__ = [
    "OWNER_PATTERN",
    "GROUP_HEADER_PATTERN",
    "REPO_LINE_PATTERN",
    "extract_owner",
    "extract_existing_repos",
    "parse_groups_and_tags",
    "get_group_folder",
    "parse_repo_tasks",
    "render_repo_groups_text",
    "add_repos_to_unclassified",
    "build_failed_repo_groups_text",
]
