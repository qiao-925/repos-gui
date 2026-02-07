from pathlib import Path

from gh_repos_sync.application.execution import run_pull_updates


def test_run_pull_updates_includes_failed_reasons(monkeypatch, tmp_path):
    tasks = [
        {
            "repo_full": "o/repo-ok",
            "repo_name": "repo-ok",
            "group_folder": "g",
            "group_name": "test-group",
            "highland": "H1",
        },
        {
            "repo_full": "o/repo-fail",
            "repo_name": "repo-fail",
            "group_folder": "g",
            "group_name": "test-group",
            "highland": "H1",
        },
    ]

    monkeypatch.setattr(
        "gh_repos_sync.application.execution.repo_config.parse_repo_groups",
        lambda _config_file: tasks,
    )

    monkeypatch.setattr(
        "gh_repos_sync.application.execution.execute_parallel_pull",
        lambda _tasks, parallel_tasks, progress_cb=None: (
            1,
            1,
            [
                {
                    "repo_full": "o/repo-fail",
                    "repo_name": "repo-fail",
                    "group_folder": "g",
                    "group_name": "test-group",
                    "highland": "H1",
                    "reason": "network_error",
                }
            ],
        ),
    )

    failed_file = tmp_path / "failed-repos.txt"

    success, result, error = run_pull_updates(
        config_file=str(tmp_path / "REPO-GROUPS.md"),
        tasks=3,
        failed_repos_file=failed_file,
    )

    assert success is True
    assert error == ""
    assert result["total"] == 2
    assert result["success"] == 1
    assert result["fail"] == 1
    assert result["failed_file"] == str(failed_file)
    assert result["failed_reasons"] == {"o/repo-fail": "network_error"}
