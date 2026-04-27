"""Unit tests for filesystem-safe repository group paths."""

from __future__ import annotations

from pathlib import Path

from clonex.domain.repo_groups import (
    get_group_folder,
    parse_repo_tasks,
    sanitize_path_segment,
)


def test_sanitize_path_segment_replaces_path_separators():
    assert sanitize_path_segment("AI / Agents") == "AI _ Agents"
    assert sanitize_path_segment(r"foo\bar:baz") == "foo_bar_baz"


def test_sanitize_path_segment_trims_windows_forbidden_suffixes():
    assert sanitize_path_segment("Group. ") == "Group"
    assert sanitize_path_segment("...") == "unnamed"


def test_get_group_folder_uses_single_safe_segment(tmp_path: Path):
    folder = get_group_folder(tmp_path, "AI / Agents")
    assert folder == tmp_path / "AI _ Agents"
    assert "Agents" == folder.name.split(" _ ")[-1]


def test_parse_repo_tasks_sanitizes_group_folder(tmp_path: Path):
    content = """# GitHub 仓库分组

仓库所有者: qiao-925

## AI / Agents
- news-digest
"""

    tasks = parse_repo_tasks(content, "qiao-925", tmp_path)

    assert len(tasks) == 1
    assert tasks[0].repo_full == "qiao-925/news-digest"
    assert tasks[0].group_name == "AI / Agents"
    assert Path(tasks[0].group_folder) == tmp_path / "AI _ Agents"
