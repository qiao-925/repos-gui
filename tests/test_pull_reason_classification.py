from gh_repos_sync.core.pull import _extract_pull_failure_reason


def test_extract_pull_failure_reason_known_cases():
    assert _extract_pull_failure_reason("fatal: not a git repository") == "not_git_repo"
    assert _extract_pull_failure_reason("fatal: couldn't find remote ref main") == "remote_ref_missing"
    assert _extract_pull_failure_reason("Your local changes to the following files would be overwritten") == "local_changes_conflict"
    assert _extract_pull_failure_reason("fatal: refusing to merge unrelated histories") == "unrelated_histories"
    assert _extract_pull_failure_reason("fatal: Not possible to fast-forward, aborting.") == "not_fast_forward"
    assert _extract_pull_failure_reason("fatal: Could not resolve host: github.com") == "network_error"
    assert _extract_pull_failure_reason("remote: Permission denied\nfatal: Authentication failed") == "auth_error"


def test_extract_pull_failure_reason_unknown_and_empty():
    assert _extract_pull_failure_reason("") == "unknown"
    assert _extract_pull_failure_reason("random unexpected stderr") == "unknown"

