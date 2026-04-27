"""Unit tests for `application.sync_with_remote`.

The function under test stitches together three remote-facing helpers:

* `infra.github_api.fetch_owner_repos`
* `gist_manager.download_config`
* `gist_manager.upload_config`

We patch those at module scope so the tests stay deterministic and
network-free.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pytest

from clonex.application import sync_with_remote
from clonex.application.sync_with_remote import sync_repos_to_gist_uncategorized
from clonex.infra.gist_config import gist_manager


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _Recorder:
    """Capture upload payloads so tests can assert on them."""

    def __init__(self) -> None:
        self.uploads: List[Dict[str, Any]] = []

    def upload(self, gist_id: str, content: str, filename: str = "REPO-GROUPS.md", token=None) -> Tuple[bool, str]:
        self.uploads.append(
            {"gist_id": gist_id, "content": content, "filename": filename}
        )
        return True, ""


def _patch_environment(monkeypatch, *, github_repos, gist_content, recorder: _Recorder, fetch_ok=True, download_ok=True):
    """Wire fakes for fetch_owner_repos / download_config / upload_config."""

    def fake_fetch_owner_repos(owner: str, token=None):
        return (fetch_ok, [{"name": n} for n in github_repos], "" if fetch_ok else "boom")

    def fake_download_config(gist_id: str, filename: str = "REPO-GROUPS.md", token=None, force_refresh: bool = False):
        return (download_ok, gist_content, "" if download_ok else "404")

    monkeypatch.setattr(sync_with_remote, "fetch_owner_repos", fake_fetch_owner_repos)
    monkeypatch.setattr(gist_manager, "download_config", fake_download_config, raising=True)
    monkeypatch.setattr(gist_manager, "upload_config", recorder.upload, raising=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


GIST_BASE = (
    "# GitHub 仓库分组\n"
    "\n"
    "仓库所有者: qiao-925\n"
    "\n"
    "## Personal\n"
    "- typing-hub\n"
    "- mobile-typing\n"
    "\n"
    "## 未分类\n"
)


def test_no_op_when_gist_already_complete(monkeypatch):
    recorder = _Recorder()
    _patch_environment(
        monkeypatch,
        github_repos=["typing-hub", "mobile-typing"],
        gist_content=GIST_BASE,
        recorder=recorder,
    )

    ok, added, content, err = sync_repos_to_gist_uncategorized(
        owner="qiao-925", gist_id="gid", token="t"
    )

    assert ok is True
    assert added == 0
    assert err == ""
    assert content == GIST_BASE
    # No upload should have happened — gist already in sync
    assert recorder.uploads == []


def test_appends_missing_repos_to_unclassified(monkeypatch):
    recorder = _Recorder()
    _patch_environment(
        monkeypatch,
        github_repos=["typing-hub", "mobile-typing", "newproject", "another"],
        gist_content=GIST_BASE,
        recorder=recorder,
    )

    ok, added, content, err = sync_repos_to_gist_uncategorized(
        owner="qiao-925", gist_id="gid", token="t"
    )

    assert ok is True
    assert added == 2
    assert err == ""
    # Both new repos should now appear in the 未分类 section of the
    # uploaded content
    assert "- newproject" in content
    assert "- another" in content
    # Original groupings must be preserved
    assert "## Personal" in content
    assert "- typing-hub" in content
    # Exactly one upload happened with the patched content
    assert len(recorder.uploads) == 1
    assert recorder.uploads[0]["gist_id"] == "gid"
    assert recorder.uploads[0]["content"] == content


def test_creates_unclassified_section_when_absent(monkeypatch):
    recorder = _Recorder()
    gist_no_unclassified = (
        "# GitHub 仓库分组\n\n仓库所有者: qiao-925\n\n## Personal\n- typing-hub\n"
    )
    _patch_environment(
        monkeypatch,
        github_repos=["typing-hub", "newrepo"],
        gist_content=gist_no_unclassified,
        recorder=recorder,
    )

    ok, added, content, err = sync_repos_to_gist_uncategorized(
        owner="qiao-925", gist_id="gid", token="t"
    )

    assert ok is True
    assert added == 1
    assert "## 未分类" in content
    assert "- newrepo" in content


def test_returns_error_when_fetch_fails(monkeypatch):
    recorder = _Recorder()
    _patch_environment(
        monkeypatch,
        github_repos=[],
        gist_content="",
        recorder=recorder,
        fetch_ok=False,
    )

    ok, added, content, err = sync_repos_to_gist_uncategorized(
        owner="qiao-925", gist_id="gid", token="t"
    )

    assert ok is False
    assert added == 0
    assert content == ""
    assert "GitHub" in err
    assert recorder.uploads == []


def test_rejects_blank_inputs():
    ok, _, _, err = sync_repos_to_gist_uncategorized(owner="", gist_id="gid")
    assert ok is False
    assert "owner" in err

    ok2, _, _, err2 = sync_repos_to_gist_uncategorized(owner="qiao-925", gist_id="")
    assert ok2 is False
    assert "gist_id" in err2
