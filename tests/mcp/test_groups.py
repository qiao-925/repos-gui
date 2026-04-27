# Tests for the B-group write_groups tool.
#
# Key regression: `write_groups` MUST be incremental — feeding it a small
# mapping must not wipe out repos already listed in REPO-GROUPS.md. This was
# a real bug during MVP development; the tests below pin the fix.

from __future__ import annotations

from pathlib import Path

import pytest

from tests.mcp.conftest import assert_err, assert_ok, call

pytestmark = pytest.mark.anyio


EXISTING_CONFIG = """# GitHub 仓库分组

仓库所有者: alice

## Go
- repo-go-a
- repo-go-b

## Python
- repo-py-a
- repo-py-b
- repo-py-c
"""


# ---------- write_groups (incremental semantics regression) ----------


async def test_write_groups_dry_run_preserves_existing_repos(
    mcp_client, tmp_path: Path
):
    """Regression: write_groups must NOT wipe repos that aren't in the new mapping."""
    config = tmp_path / "REPO-GROUPS.md"
    config.write_text(EXISTING_CONFIG, encoding="utf-8")

    payload = await call(
        mcp_client,
        "write_groups",
        {
            "mapping": {"new-repo": "Demo"},
            "path": str(config),
            "dry_run": True,
        },
    )
    data = assert_ok(payload, tool="write_groups")
    assert data["dry_run"] is True
    # 5 existing + 1 new = 6 total
    assert data["total_repos"] == 6
    assert data["updated_repos"] == 1
    preview = data["would_write_preview"]
    # Every original repo must still appear in the preview.
    for name in ("repo-go-a", "repo-go-b", "repo-py-a", "repo-py-b", "repo-py-c"):
        assert name in preview, f"{name} was lost in preview"
    assert "new-repo" in preview
    assert "Demo" in preview
    # The file on disk must not have changed.
    assert config.read_text(encoding="utf-8") == EXISTING_CONFIG


async def test_write_groups_dry_run_overwrites_existing_assignment(
    mcp_client, tmp_path: Path
):
    """Mapping an existing repo to a new group should update (not duplicate) it."""
    config = tmp_path / "REPO-GROUPS.md"
    config.write_text(EXISTING_CONFIG, encoding="utf-8")

    payload = await call(
        mcp_client,
        "write_groups",
        {
            "mapping": {"repo-go-a": "Moved"},
            "path": str(config),
            "dry_run": True,
        },
    )
    data = assert_ok(payload, tool="write_groups")
    assert data["total_repos"] == 5  # count unchanged
    assert data["updated_repos"] == 1
    preview = data["would_write_preview"]
    # repo-go-a should now be under Moved, not Go.
    moved_section = preview.split("## Moved")[1].split("## ")[0]
    assert "repo-go-a" in moved_section


async def test_write_groups_persists_when_dry_run_false(mcp_client, tmp_path: Path):
    config = tmp_path / "REPO-GROUPS.md"
    config.write_text(EXISTING_CONFIG, encoding="utf-8")

    payload = await call(
        mcp_client,
        "write_groups",
        {
            "mapping": {"brand-new": "Extra"},
            "path": str(config),
            "dry_run": False,
        },
    )
    data = assert_ok(payload, tool="write_groups")
    assert data["written"] is True
    written = config.read_text(encoding="utf-8")
    # Original repos are still present after persisting.
    assert "repo-go-a" in written
    assert "repo-py-c" in written
    # New repo appears under its new group.
    assert "brand-new" in written
    assert "## Extra" in written


async def test_write_groups_empty_mapping_is_rejected(mcp_client, tmp_path: Path):
    config = tmp_path / "REPO-GROUPS.md"
    config.write_text(EXISTING_CONFIG, encoding="utf-8")

    payload = await call(
        mcp_client,
        "write_groups",
        {"mapping": {}, "path": str(config), "dry_run": True},
    )
    assert_err(payload, tool="write_groups")


async def test_write_groups_without_owner_and_no_existing_file_errors(
    mcp_client, tmp_path: Path, monkeypatch
):
    config = tmp_path / "does-not-exist.md"
    monkeypatch.setattr(
        "clonex.mcp.tools.groups.get_cached_owner", lambda: ""
    )
    payload = await call(
        mcp_client,
        "write_groups",
        {"mapping": {"x": "G"}, "path": str(config), "dry_run": True},
    )
    assert_err(payload, "E_CONFIG_MISSING", tool="write_groups")


async def test_write_groups_refuses_when_existing_file_unparseable(
    mcp_client, tmp_path: Path, monkeypatch
):
    """Data-loss guard: if the current REPO-GROUPS.md can't be parsed,
    write_groups must surface E_INTERNAL instead of silently overwriting it
    with only the new mapping (dropping every prior repo on disk)."""
    config = tmp_path / "REPO-GROUPS.md"
    config.write_text(EXISTING_CONFIG, encoding="utf-8")
    snapshot = config.read_text(encoding="utf-8")

    def _raise(*_args, **_kwargs):
        raise RuntimeError("simulated parse failure")

    monkeypatch.setattr(
        "clonex.mcp.tools.groups.parse_repo_tasks", _raise
    )

    payload = await call(
        mcp_client,
        "write_groups",
        {
            "mapping": {"new-repo": "Demo"},
            "path": str(config),
            "dry_run": False,
        },
    )
    assert_err(payload, "E_INTERNAL", tool="write_groups")
    # File on disk must be bit-for-bit unchanged.
    assert config.read_text(encoding="utf-8") == snapshot
