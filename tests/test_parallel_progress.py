from gh_repos_sync.core.parallel import execute_parallel_clone


def test_execute_parallel_clone_reports_progress(monkeypatch):
    def fake_clone_repo(repo_full, repo_name, group_folder, parallel_connections):
        return not repo_name.endswith("-fail")

    monkeypatch.setattr("gh_repos_sync.core.parallel.clone_repo", fake_clone_repo)

    tasks = [
        {"repo_full": "o/repo1", "repo_name": "repo1", "group_folder": "g1"},
        {"repo_full": "o/repo2", "repo_name": "repo2-fail", "group_folder": "g1"},
        {"repo_full": "o/repo3", "repo_name": "repo3", "group_folder": "g2"},
    ]

    progress_calls = []

    success_count, fail_count, failed_tasks = execute_parallel_clone(
        tasks,
        parallel_tasks=2,
        parallel_connections=4,
        progress_cb=lambda done, total, success, fail: progress_calls.append((done, total, success, fail)),
    )

    assert success_count == 2
    assert fail_count == 1
    assert len(failed_tasks) == 1
    assert failed_tasks[0]["repo_full"] == "o/repo2"

    assert progress_calls[0] == (0, 3, 0, 0)
    assert len(progress_calls) == 4
    assert progress_calls[-1] == (3, 3, 2, 1)

