# Tests for the A-group read-only tools.
#
# All external side effects (keyring reads, GitHub API, file system) are
# stubbed through monkeypatch so the test suite is hermetic and fast.

from __future__ import annotations

from pathlib import Path

import pytest

from tests.mcp.conftest import assert_err, assert_ok, call

pytestmark = pytest.mark.anyio


# ---------- list_repos ----------


async def test_list_repos_success_with_cached_login(mcp_client, monkeypatch):
    fake_repos = [
        {"name": "repo-a", "private": False},
        {"name": "repo-b", "private": False},
    ]

    def fake_fetch(owner, token=None, timeout=10):
        assert owner == "cached-user"
        assert token is None  # default include_private=False ⇒ no token sent
        return True, fake_repos, ""

    monkeypatch.setattr(
        "clonex.mcp.tools.queries.get_cached_owner", lambda: "cached-user"
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.queries.get_github_token", lambda: "ghp_xxx"
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.queries.fetch_owner_repos", fake_fetch
    )

    payload = await call(mcp_client, "list_repos")
    data = assert_ok(payload, tool="list_repos")
    assert data["owner"] == "cached-user"
    assert data["count"] == 2
    assert [r["name"] for r in data["repos"]] == ["repo-a", "repo-b"]


async def test_list_repos_include_private_true_forwards_token(mcp_client, monkeypatch):
    received_tokens: list = []

    def fake_fetch(owner, token=None, timeout=10):
        received_tokens.append(token)
        return True, [], ""

    monkeypatch.setattr(
        "clonex.mcp.tools.queries.get_github_token", lambda: "ghp_real"
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.queries.fetch_owner_repos", fake_fetch
    )

    await call(
        mcp_client,
        "list_repos",
        {"owner": "alice", "include_private": True},
    )
    assert received_tokens == ["ghp_real"]


async def test_list_repos_no_owner_returns_config_missing(mcp_client, monkeypatch):
    monkeypatch.setattr(
        "clonex.mcp.tools.queries.get_cached_owner", lambda: ""
    )
    payload = await call(mcp_client, "list_repos")
    assert_err(payload, "E_CONFIG_MISSING", tool="list_repos")


async def test_list_repos_include_private_without_token_returns_auth_missing(
    mcp_client, monkeypatch
):
    monkeypatch.setattr(
        "clonex.mcp.tools.queries.get_github_token", lambda: None
    )
    payload = await call(
        mcp_client,
        "list_repos",
        {"owner": "alice", "include_private": True},
    )
    assert_err(payload, "E_AUTH_MISSING", tool="list_repos")


async def test_list_repos_propagates_github_api_error(mcp_client, monkeypatch):
    monkeypatch.setattr(
        "clonex.mcp.tools.queries.fetch_owner_repos",
        lambda owner, token=None, timeout=10: (False, [], "rate limit exceeded"),
    )
    payload = await call(mcp_client, "list_repos", {"owner": "alice"})
    error = assert_err(payload, "E_GITHUB_API", tool="list_repos")
    assert "rate limit" in error["message"]


# ---------- read_groups ----------


REPO_GROUPS_SAMPLE = """# GitHub 仓库分组

仓库所有者: demo-owner

## DemoGroup
- repo-one
- repo-two

## Another
- repo-three
"""


async def test_read_groups_parses_owner_and_assignments(mcp_client, tmp_path: Path):
    config_file = tmp_path / "REPO-GROUPS.md"
    config_file.write_text(REPO_GROUPS_SAMPLE, encoding="utf-8")

    payload = await call(mcp_client, "read_groups", {"path": str(config_file)})
    data = assert_ok(payload, tool="read_groups")
    assert data["owner"] == "demo-owner"
    by_name = {g["name"]: g for g in data["groups"]}
    assert by_name["DemoGroup"]["repos"] == ["repo-one", "repo-two"]
    assert by_name["Another"]["repos"] == ["repo-three"]


async def test_read_groups_missing_file_returns_config_missing(mcp_client, tmp_path: Path):
    missing = tmp_path / "does-not-exist.md"
    payload = await call(mcp_client, "read_groups", {"path": str(missing)})
    assert_err(payload, "E_CONFIG_MISSING", tool="read_groups")


async def test_read_groups_rejects_file_without_owner(mcp_client, tmp_path: Path):
    config_file = tmp_path / "REPO-GROUPS.md"
    config_file.write_text("# GitHub 仓库分组\n\n## SomeGroup\n", encoding="utf-8")
    payload = await call(mcp_client, "read_groups", {"path": str(config_file)})
    assert_err(payload, "E_CONFIG_MISSING", tool="read_groups")


# ---------- list_failed ----------


async def test_list_failed_returns_empty_when_file_missing(mcp_client, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "clonex.mcp.tools.queries.failed_repos_path",
        lambda: tmp_path / "never-there.txt",
    )
    payload = await call(mcp_client, "list_failed")
    data = assert_ok(payload, tool="list_failed")
    assert data["count"] == 0
    assert data["repos"] == []


async def test_list_failed_reads_existing_file(mcp_client, tmp_path, monkeypatch):
    failed_file = tmp_path / "failed-repos.txt"
    failed_file.write_text(REPO_GROUPS_SAMPLE, encoding="utf-8")

    monkeypatch.setattr(
        "clonex.mcp.tools.queries.failed_repos_path",
        lambda: failed_file,
    )
    payload = await call(mcp_client, "list_failed")
    data = assert_ok(payload, tool="list_failed")
    assert data["owner"] == "demo-owner"
    assert set(data["repos"]) == {"repo-one", "repo-two", "repo-three"}


# ---------- get_auth_status ----------


async def test_get_auth_status_fully_authenticated(mcp_client, monkeypatch):
    monkeypatch.setattr(
        "clonex.mcp.tools.queries.auth.load_token",
        lambda: ("ghp_xxx", "keyring"),
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.queries.auth.load_cached_login", lambda: "alice"
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.queries.auth.fetch_user_profile",
        lambda token: ("alice", [], ""),
    )

    payload = await call(mcp_client, "get_auth_status")
    data = assert_ok(payload, tool="get_auth_status")
    assert data["logged_in"] is True
    assert data["login_verified"] is True
    assert data["login"] == "alice"
    assert data["token_source"] == "keyring"
    assert "ai_key_configured" not in data  # AI feature removed


async def test_get_auth_status_without_token_is_logged_out(mcp_client, monkeypatch):
    monkeypatch.setattr(
        "clonex.mcp.tools.queries.auth.load_token", lambda: (None, "none")
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.queries.auth.load_cached_login", lambda: ""
    )

    payload = await call(mcp_client, "get_auth_status")
    data = assert_ok(payload, tool="get_auth_status")
    assert data["logged_in"] is False
    assert data["login_verified"] is False


async def test_get_auth_status_invalid_token_is_unverified(mcp_client, monkeypatch):
    monkeypatch.setattr(
        "clonex.mcp.tools.queries.auth.load_token",
        lambda: ("ghp_stale", "keyring"),
    )
    monkeypatch.setattr(
        "clonex.mcp.tools.queries.auth.load_cached_login", lambda: "cached"
    )
    # fetch_user_profile returns no login ⇒ token didn't verify.
    monkeypatch.setattr(
        "clonex.mcp.tools.queries.auth.fetch_user_profile",
        lambda token: ("", [], "401 unauthorized"),
    )

    payload = await call(mcp_client, "get_auth_status")
    data = assert_ok(payload, tool="get_auth_status")
    assert data["logged_in"] is True  # token is present
    assert data["login_verified"] is False
    assert data["login"] == "cached"  # falls back to cached login
