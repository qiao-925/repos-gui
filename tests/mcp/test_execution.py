# Tests for the C-group single-repo execution tools.

from __future__ import annotations

from pathlib import Path

import pytest

from tests.mcp.conftest import assert_err, assert_ok, call

pytestmark = pytest.mark.anyio


def _make_fake_git_repo(root: Path, name: str) -> Path:
    """Create a directory that looks like a git repo (has a .git child)."""
    repo = root / name
    (repo / ".git").mkdir(parents=True)
    return repo


# ---------- clone_repo ----------


async def test_clone_repo_dry_run_by_default_does_not_execute(
    mcp_client, monkeypatch
):
    executed: list = []

    def fake_clone(*args, **kwargs):
        executed.append(args)
        return True

    monkeypatch.setattr(
        "clonex.mcp.tools.execution.clone_mod.clone_repo", fake_clone
    )

    payload = await call(
        mcp_client, "clone_repo", {"owner": "alice", "repo": "demo"}
    )
    data = assert_ok(payload, tool="clone_repo")
    assert data["dry_run"] is True
    assert data["would_execute"]["repo_full"] == "alice/demo"
    assert data["would_execute"]["repo_name"] == "demo"
    assert executed == [], "clone_repo must not execute when dry_run is True"


async def test_clone_repo_missing_owner_returns_invalid_arg(mcp_client):
    payload = await call(mcp_client, "clone_repo", {"owner": "", "repo": "demo"})
    assert_err(payload, "E_INVALID_ARG", tool="clone_repo")


async def test_clone_repo_actually_calls_core_when_dry_run_false(
    mcp_client, tmp_path: Path, monkeypatch
):
    captured: dict = {}

    def fake_clone(repo_full, repo_name, folder, parallel, token):
        captured.update(
            repo_full=repo_full,
            repo_name=repo_name,
            folder=folder,
            parallel=parallel,
            token=token,
        )
        return True

    monkeypatch.setattr(
        "clonex.mcp.tools.execution.get_github_token", lambda: "ghp_xxx"
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.execution.clone_mod.clone_repo", fake_clone
    )

    payload = await call(
        mcp_client,
        "clone_repo",
        {
            "owner": "alice",
            "repo": "demo",
            "group_folder": str(tmp_path),
            "parallel_connections": 4,
            "dry_run": False,
        },
    )
    data = assert_ok(payload, tool="clone_repo")
    assert data["cloned"] is True
    assert captured == {
        "repo_full": "alice/demo",
        "repo_name": "demo",
        "folder": str(tmp_path),
        "parallel": 4,
        "token": "ghp_xxx",
    }


async def test_clone_repo_returns_git_exec_error_on_failure(
    mcp_client, tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(
        "clonex.mcp.tools.execution.clone_mod.clone_repo",
        lambda *args, **kwargs: False,
    )
    payload = await call(
        mcp_client,
        "clone_repo",
        {
            "owner": "alice",
            "repo": "demo",
            "group_folder": str(tmp_path),
            "dry_run": False,
        },
    )
    assert_err(payload, "E_GIT_EXEC", tool="clone_repo")


# ---------- pull_repo ----------


async def test_pull_repo_dry_run_by_default(mcp_client, tmp_path: Path):
    repo = _make_fake_git_repo(tmp_path, "demo")
    payload = await call(mcp_client, "pull_repo", {"repo_path": str(repo)})
    data = assert_ok(payload, tool="pull_repo")
    assert data["dry_run"] is True
    assert data["would_pull"] == str(repo)


async def test_pull_repo_missing_path_returns_invalid_arg(mcp_client):
    payload = await call(mcp_client, "pull_repo", {"repo_path": ""})
    assert_err(payload, "E_INVALID_ARG", tool="pull_repo")


async def test_pull_repo_non_git_directory_returns_invalid_arg(
    mcp_client, tmp_path: Path
):
    not_a_repo = tmp_path / "plain-dir"
    not_a_repo.mkdir()
    payload = await call(mcp_client, "pull_repo", {"repo_path": str(not_a_repo)})
    assert_err(payload, "E_INVALID_ARG", tool="pull_repo")


async def test_pull_repo_success_path(mcp_client, tmp_path: Path, monkeypatch):
    repo = _make_fake_git_repo(tmp_path, "demo")

    monkeypatch.setattr(
        "clonex.mcp.tools.execution.get_github_token", lambda: None
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.execution.pull_mod.pull_repo",
        lambda *args, **kwargs: (True, ""),
    )

    payload = await call(
        mcp_client, "pull_repo", {"repo_path": str(repo), "dry_run": False}
    )
    data = assert_ok(payload, tool="pull_repo")
    assert data["updated"] is True


async def test_pull_repo_failure_path(mcp_client, tmp_path: Path, monkeypatch):
    repo = _make_fake_git_repo(tmp_path, "demo")

    monkeypatch.setattr(
        "clonex.mcp.tools.execution.pull_mod.pull_repo",
        lambda *args, **kwargs: (False, "non-fast-forward"),
    )

    payload = await call(
        mcp_client, "pull_repo", {"repo_path": str(repo), "dry_run": False}
    )
    error = assert_err(payload, "E_GIT_EXEC", tool="pull_repo")
    assert "non-fast-forward" in error["message"]


# ---------- check_repo ----------


async def test_check_repo_missing_path_returns_invalid_arg(mcp_client):
    payload = await call(mcp_client, "check_repo", {"repo_path": ""})
    assert_err(payload, "E_INVALID_ARG", tool="check_repo")


async def test_check_repo_non_existent_path_returns_invalid_arg(
    mcp_client, tmp_path: Path
):
    missing = tmp_path / "nope"
    payload = await call(mcp_client, "check_repo", {"repo_path": str(missing)})
    assert_err(payload, "E_INVALID_ARG", tool="check_repo")


async def test_check_repo_valid_result(mcp_client, tmp_path: Path, monkeypatch):
    repo = _make_fake_git_repo(tmp_path, "demo")
    monkeypatch.setattr(
        "clonex.mcp.tools.execution.check_mod.check_repo",
        lambda path, label, timeout: (True, ""),
    )
    payload = await call(mcp_client, "check_repo", {"repo_path": str(repo)})
    data = assert_ok(payload, tool="check_repo")
    assert data["valid"] is True
    assert data["error"] == ""


async def test_check_repo_invalid_result_surfaces_error(
    mcp_client, tmp_path: Path, monkeypatch
):
    repo = _make_fake_git_repo(tmp_path, "demo")
    monkeypatch.setattr(
        "clonex.mcp.tools.execution.check_mod.check_repo",
        lambda path, label, timeout: (False, "dangling object abc123"),
    )
    payload = await call(
        mcp_client,
        "check_repo",
        {"repo_path": str(repo), "expected_repo_full": "alice/demo", "timeout": 10},
    )
    data = assert_ok(payload, tool="check_repo")
    assert data["valid"] is False
    assert "dangling" in data["error"]
