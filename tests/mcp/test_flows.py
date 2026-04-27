# Tests for the D-group high-level workflow tools.

from __future__ import annotations

from pathlib import Path

import pytest

from tests.mcp.conftest import assert_err, assert_ok, call

pytestmark = pytest.mark.anyio


SAMPLE_REPO_GROUPS = """# GitHub 仓库分组

仓库所有者: alice

## Tools
- demo-tool-a
- demo-tool-b

## Libs
- demo-lib-a
"""


# ---------- clone_group ----------


async def test_clone_group_requires_existing_config(mcp_client, tmp_path: Path):
    missing = tmp_path / "nope.md"
    payload = await call(
        mcp_client,
        "clone_group",
        {"group_name": "Tools", "config_file": str(missing)},
    )
    assert_err(payload, "E_CONFIG_MISSING", tool="clone_group")


async def test_clone_group_unknown_group_returns_invalid_arg(mcp_client, tmp_path: Path):
    config = tmp_path / "REPO-GROUPS.md"
    config.write_text(SAMPLE_REPO_GROUPS, encoding="utf-8")
    payload = await call(
        mcp_client,
        "clone_group",
        {"group_name": "NonExistent", "config_file": str(config)},
    )
    assert_err(payload, "E_INVALID_ARG", tool="clone_group")


async def test_clone_group_dry_run_returns_filtered_tasks(mcp_client, tmp_path: Path):
    config = tmp_path / "REPO-GROUPS.md"
    config.write_text(SAMPLE_REPO_GROUPS, encoding="utf-8")
    payload = await call(
        mcp_client,
        "clone_group",
        {"group_name": "Tools", "config_file": str(config)},
    )
    data = assert_ok(payload, tool="clone_group")
    assert data["dry_run"] is True
    assert data["count"] == 2
    names = {t["repo_name"] for t in data["would_execute"]}
    assert names == {"demo-tool-a", "demo-tool-b"}


async def test_clone_group_executes_when_dry_run_false(
    mcp_client, tmp_path: Path, monkeypatch
):
    config = tmp_path / "REPO-GROUPS.md"
    config.write_text(SAMPLE_REPO_GROUPS, encoding="utf-8")

    captured: dict = {}

    def fake_execute(tasks, parallel_tasks, parallel_connections, token, cb):
        captured["n"] = len(tasks)
        return 2, 0, []

    monkeypatch.setattr(
        "clonex.mcp.tools.flows.get_github_token", lambda: None
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.flows.execute_parallel_clone", fake_execute
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.flows.save_failed_repos",
        lambda failed, path, owner: None,  # should not be called (no failures)
    )

    payload = await call(
        mcp_client,
        "clone_group",
        {
            "group_name": "Tools",
            "config_file": str(config),
            "dry_run": False,
        },
    )
    data = assert_ok(payload, tool="clone_group")
    assert data["success"] == 2
    assert data["fail"] == 0
    assert captured["n"] == 2


# ---------- update_all ----------


async def test_update_all_requires_existing_config(mcp_client, tmp_path: Path):
    missing = tmp_path / "nope.md"
    payload = await call(mcp_client, "update_all", {"config_file": str(missing)})
    assert_err(payload, "E_CONFIG_MISSING", tool="update_all")


async def test_update_all_dry_run_counts_all_tasks(mcp_client, tmp_path: Path):
    config = tmp_path / "REPO-GROUPS.md"
    config.write_text(SAMPLE_REPO_GROUPS, encoding="utf-8")
    payload = await call(mcp_client, "update_all", {"config_file": str(config)})
    data = assert_ok(payload, tool="update_all")
    assert data["dry_run"] is True
    assert data["count"] == 3  # 2 Tools + 1 Libs


async def test_update_all_executes_when_dry_run_false(
    mcp_client, tmp_path: Path, monkeypatch
):
    config = tmp_path / "REPO-GROUPS.md"
    config.write_text(SAMPLE_REPO_GROUPS, encoding="utf-8")

    monkeypatch.setattr(
        "clonex.mcp.tools.flows.get_github_token", lambda: None
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.flows.execute_parallel_pull",
        lambda tasks, parallel, token, cb: (3, 0, []),
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.flows.save_failed_repos",
        lambda failed, path, owner: None,
    )

    payload = await call(
        mcp_client,
        "update_all",
        {"config_file": str(config), "dry_run": False},
    )
    data = assert_ok(payload, tool="update_all")
    assert data["total"] == 3
    assert data["success"] == 3


# ---------- retry_failed ----------


async def test_retry_failed_with_no_failed_file_returns_empty(
    mcp_client, tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(
        "clonex.mcp.tools.flows.failed_repos_path",
        lambda: tmp_path / "never-there.txt",
    )
    payload = await call(mcp_client, "retry_failed", {})
    data = assert_ok(payload, tool="retry_failed")
    assert data["total"] == 0


async def test_retry_failed_dry_run_lists_tasks(mcp_client, tmp_path: Path, monkeypatch):
    failed_file = tmp_path / "failed-repos.txt"
    failed_file.write_text(SAMPLE_REPO_GROUPS, encoding="utf-8")

    monkeypatch.setattr(
        "clonex.mcp.tools.flows.failed_repos_path", lambda: failed_file
    )

    payload = await call(mcp_client, "retry_failed", {})
    data = assert_ok(payload, tool="retry_failed")
    assert data["dry_run"] is True
    assert data["count"] == 3


async def test_retry_failed_executes_and_rewrites_list(
    mcp_client, tmp_path: Path, monkeypatch
):
    failed_file = tmp_path / "failed-repos.txt"
    failed_file.write_text(SAMPLE_REPO_GROUPS, encoding="utf-8")

    saved: dict = {}

    def fake_save(failed, path, owner):
        saved["count"] = len(failed)
        saved["path"] = path

    monkeypatch.setattr(
        "clonex.mcp.tools.flows.failed_repos_path", lambda: failed_file
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.flows.get_github_token", lambda: None
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.flows.execute_parallel_clone",
        lambda tasks, parallel_t, parallel_c, token, cb: (
            2,
            1,
            [tasks[0]],  # one task still failed
        ),
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.flows.save_failed_repos", fake_save
    )

    payload = await call(
        mcp_client, "retry_failed", {"dry_run": False}
    )
    data = assert_ok(payload, tool="retry_failed")
    assert data["success"] == 2
    assert data["fail"] == 1
    # Rewriting is always called so the list reflects current state.
    assert saved["count"] == 1
