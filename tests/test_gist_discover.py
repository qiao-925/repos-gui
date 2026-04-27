"""Unit tests for the auto-discover/auto-create flow in `infra.gist_config`."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from clonex.infra.gist_config import GistConfigManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_manager(tmp_path: Path) -> GistConfigManager:
    """Build an isolated manager that writes to `tmp_path` only."""
    return GistConfigManager(cache_dir=tmp_path / "gist_cache")


def patch_token(monkeypatch, token: Optional[str] = "fake-token") -> None:
    """Force `_get_token` to return a deterministic value (no keyring access)."""

    def fake(self, provided_token: Optional[str] = None) -> Optional[str]:
        return provided_token or token

    monkeypatch.setattr(GistConfigManager, "_get_token", fake, raising=True)


# ---------------------------------------------------------------------------
# active_gist_id round-trip
# ---------------------------------------------------------------------------


def test_active_gist_id_default_none(tmp_path: Path):
    mgr = make_manager(tmp_path)
    assert mgr.get_active_gist_id() is None


def test_active_gist_id_set_then_get(tmp_path: Path):
    mgr = make_manager(tmp_path)
    mgr.set_active_gist_id("abc123")
    assert mgr.get_active_gist_id() == "abc123"


def test_active_gist_id_persists_across_instances(tmp_path: Path):
    mgr1 = make_manager(tmp_path)
    mgr1.set_active_gist_id("persisted-id")

    mgr2 = make_manager(tmp_path)
    assert mgr2.get_active_gist_id() == "persisted-id"


def test_active_gist_id_handles_corrupt_meta(tmp_path: Path):
    mgr = make_manager(tmp_path)
    # Force broken meta shape; method should degrade gracefully
    mgr.config_cache[mgr.META_KEY] = "not a dict"
    assert mgr.get_active_gist_id() is None


# ---------------------------------------------------------------------------
# discover_or_create_repo_groups_gist
# ---------------------------------------------------------------------------


def test_discover_uses_cached_active_id_when_valid(tmp_path: Path, monkeypatch):
    mgr = make_manager(tmp_path)
    mgr.set_active_gist_id("cached-id")
    patch_token(monkeypatch)

    calls: Dict[str, int] = {"get_content": 0, "list_user": 0, "create": 0}

    def fake_get_content(self, gist_id: str, filename: str, token=None) -> Tuple[bool, str, str]:
        calls["get_content"] += 1
        assert gist_id == "cached-id"
        return True, "# stub\n", ""

    def fake_list_user_gists(self, token=None):
        calls["list_user"] += 1
        return True, [], ""

    def fake_create(*args, **kwargs):
        calls["create"] += 1
        return True, "should-not-be-called", "x"

    monkeypatch.setattr(GistConfigManager, "_get_gist_content", fake_get_content, raising=True)
    monkeypatch.setattr(GistConfigManager, "list_user_gists", fake_list_user_gists, raising=True)
    monkeypatch.setattr(GistConfigManager, "create_gist", fake_create, raising=True)

    ok, gist_id, gist_url, was_created, err = mgr.discover_or_create_repo_groups_gist(owner="qiao-925")

    assert ok is True
    assert gist_id == "cached-id"
    assert was_created is False
    assert err == ""
    assert "qiao-925" in gist_url and "cached-id" in gist_url
    assert calls == {"get_content": 1, "list_user": 0, "create": 0}


def test_discover_falls_back_to_search_when_cache_stale(tmp_path: Path, monkeypatch):
    mgr = make_manager(tmp_path)
    mgr.set_active_gist_id("stale-id")
    patch_token(monkeypatch)

    def fake_get_content(self, gist_id: str, filename: str, token=None) -> Tuple[bool, str, str]:
        # Cache miss
        return False, "", "404"

    found_gist = {
        "id": "found-id",
        "url": "https://gist.github.com/qiao-925/found-id",
        "description": "",
        "updated_at": "now",
    }

    def fake_list_user_gists(self, token=None) -> Tuple[bool, List[Dict[str, Any]], str]:
        return True, [{"id": "found-id", "files": {"REPO-GROUPS.md": {}}}], ""

    def fake_find_config_gist(self, gists, filename="REPO-GROUPS.md"):
        return found_gist

    monkeypatch.setattr(GistConfigManager, "_get_gist_content", fake_get_content, raising=True)
    monkeypatch.setattr(GistConfigManager, "list_user_gists", fake_list_user_gists, raising=True)
    monkeypatch.setattr(GistConfigManager, "find_config_gist", fake_find_config_gist, raising=True)

    ok, gist_id, gist_url, was_created, err = mgr.discover_or_create_repo_groups_gist(owner="qiao-925")

    assert ok is True
    assert gist_id == "found-id"
    assert was_created is False
    assert gist_url == "https://gist.github.com/qiao-925/found-id"
    # Cache should now point at the freshly discovered id
    assert mgr.get_active_gist_id() == "found-id"


def test_discover_creates_when_no_match_found(tmp_path: Path, monkeypatch):
    mgr = make_manager(tmp_path)
    patch_token(monkeypatch)

    def fake_list_user_gists(self, token=None):
        return True, [], ""

    def fake_find_config_gist(self, gists, filename="REPO-GROUPS.md"):
        return None

    captured: Dict[str, Any] = {}

    def fake_create(self, content, filename="REPO-GROUPS.md", token=None, description=None, public=False):
        captured["content"] = content
        captured["filename"] = filename
        captured["public"] = public
        return True, "new-id", "https://gist.github.com/qiao-925/new-id"

    monkeypatch.setattr(GistConfigManager, "list_user_gists", fake_list_user_gists, raising=True)
    monkeypatch.setattr(GistConfigManager, "find_config_gist", fake_find_config_gist, raising=True)
    monkeypatch.setattr(GistConfigManager, "create_gist", fake_create, raising=True)

    ok, gist_id, gist_url, was_created, err = mgr.discover_or_create_repo_groups_gist(owner="qiao-925")

    assert ok is True
    assert gist_id == "new-id"
    assert was_created is True
    assert err == ""
    assert mgr.get_active_gist_id() == "new-id"
    assert captured["filename"] == "REPO-GROUPS.md"
    assert captured["public"] is False
    assert "仓库所有者: qiao-925" in captured["content"]
    assert "## 未分类" in captured["content"]


def test_discover_propagates_list_failure(tmp_path: Path, monkeypatch):
    mgr = make_manager(tmp_path)
    patch_token(monkeypatch)

    def fake_list_user_gists(self, token=None):
        return False, [], "rate limited"

    monkeypatch.setattr(GistConfigManager, "list_user_gists", fake_list_user_gists, raising=True)

    ok, gist_id, gist_url, was_created, err = mgr.discover_or_create_repo_groups_gist(owner="qiao-925")

    assert ok is False
    assert gist_id == ""
    assert was_created is False
    assert "rate limited" in err
