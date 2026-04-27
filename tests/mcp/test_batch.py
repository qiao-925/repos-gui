# Tests for the C2-group batch execution tools.

from __future__ import annotations

import pytest

from tests.mcp.conftest import assert_err, assert_ok, call

pytestmark = pytest.mark.anyio


SAMPLE_TASK = {
    "repo_full": "alice/demo",
    "repo_name": "demo",
    "group_folder": "/tmp/demo-group",
    "group_name": "Demo",
    "highland": "",
}


# ---------- clone_repos_batch ----------


async def test_clone_repos_batch_empty_tasks_rejected(mcp_client):
    payload = await call(mcp_client, "clone_repos_batch", {"tasks": []})
    assert_err(payload, "E_INVALID_ARG", tool="clone_repos_batch")


async def test_clone_repos_batch_task_missing_required_field(mcp_client):
    payload = await call(
        mcp_client,
        "clone_repos_batch",
        {"tasks": [{"repo_full": "alice/demo"}]},  # missing repo_name, group_folder
    )
    error = assert_err(payload, "E_INVALID_ARG", tool="clone_repos_batch")
    assert "repo_name" in error["message"] or "group_folder" in error["message"]


async def test_clone_repos_batch_dry_run_preview(mcp_client):
    payload = await call(
        mcp_client, "clone_repos_batch", {"tasks": [SAMPLE_TASK]}
    )
    data = assert_ok(payload, tool="clone_repos_batch")
    assert data["dry_run"] is True
    assert data["count"] == 1
    assert data["would_execute"][0]["repo_full"] == "alice/demo"


async def test_clone_repos_batch_executes_when_dry_run_false(mcp_client, monkeypatch):
    captured: dict = {}

    def fake_execute(tasks, parallel_tasks, parallel_connections, token, cb):
        captured.update(
            n=len(tasks),
            parallel_tasks=parallel_tasks,
            parallel_connections=parallel_connections,
            token=token,
        )
        return 2, 1, [{"repo_full": "alice/broken", "repo_name": "broken"}]

    monkeypatch.setattr(
        "clonex.mcp.tools.batch.get_github_token", lambda: "ghp_xxx"
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.batch.execute_parallel_clone", fake_execute
    )

    payload = await call(
        mcp_client,
        "clone_repos_batch",
        {
            "tasks": [SAMPLE_TASK, SAMPLE_TASK, SAMPLE_TASK],
            "parallel_tasks": 2,
            "parallel_connections": 6,
            "dry_run": False,
        },
    )
    data = assert_ok(payload, tool="clone_repos_batch")
    assert data["total"] == 3
    assert data["success"] == 2
    assert data["fail"] == 1
    assert len(data["failed_tasks"]) == 1
    assert captured == {
        "n": 3,
        "parallel_tasks": 2,
        "parallel_connections": 6,
        "token": "ghp_xxx",
    }


# ---------- pull_repos_batch ----------


async def test_pull_repos_batch_dry_run_preview(mcp_client):
    payload = await call(mcp_client, "pull_repos_batch", {"tasks": [SAMPLE_TASK]})
    data = assert_ok(payload, tool="pull_repos_batch")
    assert data["dry_run"] is True
    assert data["count"] == 1


async def test_pull_repos_batch_executes_when_dry_run_false(mcp_client, monkeypatch):
    monkeypatch.setattr(
        "clonex.mcp.tools.batch.get_github_token", lambda: None
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.batch.execute_parallel_pull",
        lambda *args, **kwargs: (1, 0, []),
    )

    payload = await call(
        mcp_client,
        "pull_repos_batch",
        {"tasks": [SAMPLE_TASK], "dry_run": False},
    )
    data = assert_ok(payload, tool="pull_repos_batch")
    assert data["total"] == 1
    assert data["success"] == 1
    assert data["fail"] == 0


async def test_pull_repos_batch_rejects_task_missing_fields(mcp_client):
    payload = await call(
        mcp_client,
        "pull_repos_batch",
        {"tasks": [{"repo_full": "alice/demo"}]},  # missing repo_name + group_folder
    )
    error = assert_err(payload, "E_INVALID_ARG", tool="pull_repos_batch")
    assert "repo_name" in error["message"] or "group_folder" in error["message"]


# ---------- check_repos_batch (read-only, no dry_run) ----------


async def test_check_repos_batch_rejects_empty_list(mcp_client):
    payload = await call(mcp_client, "check_repos_batch", {"tasks": []})
    assert_err(payload, "E_INVALID_ARG", tool="check_repos_batch")


async def test_check_repos_batch_reports_success_and_failures(
    mcp_client, monkeypatch
):
    def fake_check(tasks, parallel, timeout, cb):
        return 1, 1, [{"repo_full": "alice/bad", "repo_name": "bad"}]

    monkeypatch.setattr(
        "clonex.mcp.tools.batch.check_repos_parallel", fake_check
    )

    payload = await call(
        mcp_client,
        "check_repos_batch",
        {"tasks": [SAMPLE_TASK, SAMPLE_TASK], "parallel_tasks": 3, "timeout": 15},
    )
    data = assert_ok(payload, tool="check_repos_batch")
    assert data["total"] == 2
    assert data["success"] == 1
    assert data["fail"] == 1
    assert len(data["failed_tasks"]) == 1
