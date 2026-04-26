"""Unit tests for `core.workspace` (.code-workspace generation)."""

from __future__ import annotations

import json
from pathlib import Path

from gh_repos_sync.core.workspace import (
    build_workspace_payload,
    sanitize_workspace_filename,
    write_workspace_file,
)


# ---------------------------------------------------------------------------
# sanitize_workspace_filename
# ---------------------------------------------------------------------------


def test_sanitize_replaces_path_separators_and_collapses():
    assert sanitize_workspace_filename("AI / Agents") == "AI _ Agents"
    assert sanitize_workspace_filename("a/b\\c:d") == "a_b_c_d"


def test_sanitize_preserves_chinese_and_spaces():
    assert sanitize_workspace_filename("个人 数据") == "个人 数据"


def test_sanitize_collapses_consecutive_replacements():
    # "A//B" -> "A__B" then collapsed to "A_B"
    assert sanitize_workspace_filename("A//B") == "A_B"


def test_sanitize_blank_input_falls_back():
    assert sanitize_workspace_filename("") == "workspace"
    assert sanitize_workspace_filename("   ") == "workspace"


# ---------------------------------------------------------------------------
# build_workspace_payload
# ---------------------------------------------------------------------------


def test_payload_uses_relative_paths():
    payload = build_workspace_payload(["repo-a", "repo-b"])
    assert payload == {
        "folders": [
            {"path": "./repo-a"},
            {"path": "./repo-b"},
        ],
        "settings": {},
    }


def test_payload_skips_empty_and_dedupes():
    payload = build_workspace_payload(["a", "", "  ", "b", "a"])
    assert [f["path"] for f in payload["folders"]] == ["./a", "./b"]


def test_payload_handles_empty_input():
    assert build_workspace_payload([]) == {"folders": [], "settings": {}}


# ---------------------------------------------------------------------------
# write_workspace_file
# ---------------------------------------------------------------------------


def test_write_workspace_creates_file_with_relative_paths(tmp_path: Path):
    group_dir = tmp_path / "Personal"
    group_dir.mkdir()
    (group_dir / "typing-hub").mkdir()
    (group_dir / "mobile-typing").mkdir()

    ok, written = write_workspace_file(group_dir, "Personal", ["typing-hub", "mobile-typing"])
    assert ok is True
    target = group_dir / "Personal.code-workspace"
    assert target.exists()
    assert Path(written) == target

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["folders"] == [
        {"path": "./typing-hub"},
        {"path": "./mobile-typing"},
    ]


def test_write_workspace_sanitizes_group_name(tmp_path: Path):
    group_dir = tmp_path / "AI _ Agents"
    group_dir.mkdir()
    ok, written = write_workspace_file(group_dir, "AI / Agents", ["bot"])
    assert ok is True
    assert Path(written).name == "AI _ Agents.code-workspace"


def test_write_workspace_skips_when_no_repos(tmp_path: Path):
    group_dir = tmp_path / "Empty"
    group_dir.mkdir()
    ok, msg = write_workspace_file(group_dir, "Empty", [])
    assert ok is False
    assert msg == "no folders"
    # Should not write anything
    assert list(group_dir.iterdir()) == []


def test_write_workspace_fails_for_missing_directory(tmp_path: Path):
    missing = tmp_path / "does-not-exist"
    ok, msg = write_workspace_file(missing, "Foo", ["bar"])
    assert ok is False
    assert "not a directory" in msg
