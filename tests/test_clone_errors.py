from clonex.core.clone import _extract_git_error_detail


def test_extract_git_error_detail_prefers_error_lines():
    stderr = """
Updating files: 100% (10/10), done.
error: invalid path 'docs/foo:bar.md'
fatal: unable to checkout working tree
warning: Clone succeeded, but checkout failed.
you can inspect what was checked out with 'git status'
and retry with 'git restore --source=HEAD :/'
"""

    detail = _extract_git_error_detail(stderr)

    assert "error: invalid path 'docs/foo:bar.md'" in detail
    assert "fatal: unable to checkout working tree" in detail
    assert "git restore" not in detail


def test_extract_git_error_detail_falls_back_to_last_line():
    assert _extract_git_error_detail("first\nlast") == "last"


def test_extract_git_error_detail_truncates_long_message():
    detail = _extract_git_error_detail("error: " + "x" * 100, max_length=20)

    assert len(detail) == 20
    assert detail.endswith("…")
