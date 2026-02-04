# GUI workers (threaded tasks)

import time
from typing import Dict, List

from PyQt5.QtCore import QThread, pyqtSignal

from lib import config, github_api, repo_groups
from lib.check import check_repos_parallel
from lib.failed_repos import save_failed_repos
from lib.logger import get_log_state, set_log_callback
from lib.parallel import execute_parallel_clone
from lib.sync import apply_sync, preview_sync
from lib.config import parse_repo_groups
from lib import ai
from app.constants import CHECK_TIMEOUT, FAILED_REPOS_FILE

class SyncWorker(QThread):
    """同步预览工作线程"""
    finished = pyqtSignal(bool, str, list, str)  # 成功标志, owner, 新增仓库列表, 错误信息

    def __init__(self, config_file: str, owner_override: str = "", token: str = ""):
        super().__init__()
        self.config_file = config_file
        self.owner_override = owner_override
        self.token = token

    def run(self):
        success, owner, new_repos, error = preview_sync(
            self.config_file,
            owner_override=self.owner_override or None,
            token=self.token or None
        )
        self.finished.emit(success, owner, new_repos, error)


class ApplyWorker(QThread):
    """应用同步工作线程"""
    finished = pyqtSignal(bool, str)  # 成功标志, 错误信息

    def __init__(self, config_file: str, new_repos: List[str]):
        super().__init__()
        self.config_file = config_file
        self.new_repos = new_repos

    def run(self):
        success, error = apply_sync(self.config_file, self.new_repos)
        self.finished.emit(success, error)


class AuthWorker(QThread):
    """GitHub 设备授权工作线程"""
    code_ready = pyqtSignal(str, str)  # user_code, verification_url
    finished = pyqtSignal(bool, str, str, int, str)  # 成功标志, token, login, public_repos, 错误信息

    def __init__(self, client_id: str):
        super().__init__()
        self.client_id = client_id

    def run(self):
        success, data, error = auth.request_device_code(self.client_id)
        if not success:
            self.finished.emit(False, "", "", -1, error)
            return

        verification_url = data.get("verification_uri_complete") or data.get("verification_uri", "")
        user_code = data.get("user_code", "")
        if verification_url:
            auth.open_verification_page(verification_url)
        if user_code:
            self.code_ready.emit(user_code, verification_url)

        token, error = auth.poll_for_token(
            self.client_id,
            data.get("device_code", ""),
            data.get("interval", 5),
            data.get("expires_in", 900)
        )
        if not token:
            self.finished.emit(False, "", "", -1, error)
            return

        login, public_repos, login_error = auth.fetch_user_profile(token)
        if login_error:
            self.finished.emit(True, token, "", -1, login_error)
            return

        self.finished.emit(True, token, login or "", public_repos, "")


class ProfileWorker(QThread):
    """刷新账号信息线程"""
    finished = pyqtSignal(bool, str, int, str)  # 成功标志, login, public_repos, 错误信息

    def __init__(self, token: str):
        super().__init__()
        self.token = token

    def run(self):
        login, public_repos, error = auth.fetch_user_profile(self.token)
        if error:
            self.finished.emit(False, "", -1, error)
            return
        self.finished.emit(True, login or "", public_repos, "")


class RepoFetchWorker(QThread):
    """拉取仓库列表线程"""
    finished = pyqtSignal(bool, list, str)  # 成功标志, repos, 错误信息

    def __init__(self, owner: str, token: str):
        super().__init__()
        self.owner = owner
        self.token = token

    def run(self):
        success, repos, error = github_api.fetch_public_repos(self.owner, token=self.token or None)
        self.finished.emit(success, repos, error)


class AiClassifyWorker(QThread):
    """AI 分类线程"""
    progress = pyqtSignal(int, int)  # 当前块, 总块
    finished = pyqtSignal(bool, dict, str)  # 成功标志, mapping, 错误信息

    def __init__(self, repos: List[Dict[str, object]], groups: List[str], api_key: str, base_url: str, model: str):
        super().__init__()
        self.repos = repos
        self.groups = groups
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def run(self):
        def _progress(done: int, total: int) -> None:
            self.progress.emit(done, total)

        mapping, error = ai.classify_repos(
            self.repos,
            self.groups,
            self.api_key,
            base_url=self.base_url,
            model=self.model,
            progress_cb=_progress
        )
        if error:
            self.finished.emit(False, {}, error)
            return
        self.finished.emit(True, mapping, "")


class AiGenerateWorker(QThread):
    """AI 自动分类并生成 REPO-GROUPS.md"""
    progress = pyqtSignal(int, int)  # 当前块, 总块
    finished = pyqtSignal(bool, int, str)  # 成功标志, 仓库数, 错误信息

    def __init__(
        self,
        owner: str,
        token: str,
        config_file: str,
        groups: List[str],
        tags: Dict[str, str],
        api_key: str,
        base_url: str,
        model: str
    ):
        super().__init__()
        self.owner = owner
        self.token = token
        self.config_file = config_file
        self.groups = groups
        self.tags = tags
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def run(self):
        success, repos, error = github_api.fetch_public_repos(self.owner, token=self.token or None)
        if not success:
            self.finished.emit(False, 0, error)
            return

        def _progress(done: int, total: int) -> None:
            self.progress.emit(done, total)

        mapping, error = ai.classify_repos(
            repos,
            [],
            self.api_key,
            base_url=self.base_url,
            model=self.model,
            progress_cb=_progress
        )
        if error:
            self.finished.emit(False, 0, error)
            return

        assignments: Dict[str, str] = {}
        for repo in repos:
            name = str(repo.get("name", "")).strip()
            if not name:
                continue
            group = mapping.get(name, "").strip() or "未分类"
            assignments[name] = group

        groups = sorted({group for group in assignments.values() if group})

        ok, error = repo_groups.write_repo_groups(
            self.config_file,
            self.owner,
            groups,
            assignments,
            self.tags,
            keep_empty=True
        )
        if not ok:
            self.finished.emit(False, 0, error)
            return

        self.finished.emit(True, len(repos), "")



class CloneWorker(QThread):
    """克隆 + 完整性检查工作线程"""
    finished = pyqtSignal(bool, dict, str)  # 成功标志, 结果, 错误信息
    log_signal = pyqtSignal(str)

    def __init__(self, config_file: str, tasks: int, connections: int):
        super().__init__()
        self.config_file = config_file
        self.tasks = tasks
        self.connections = connections

    def _log_callback(self, level: str, message: str, timestamp: str) -> None:
        self.log_signal.emit(f"[{level}] [{timestamp}] {message}")

    def run(self):
        prev_callback, prev_stdout, prev_stderr = get_log_state()
        set_log_callback(self._log_callback, log_to_stdout=False, log_to_stderr=False)

        try:
            start_time = time.time()
            tasks = parse_repo_groups(self.config_file)
            if not tasks:
                raise ValueError("未找到任何仓库任务")

            total_repos = len(tasks)

            if FAILED_REPOS_FILE.exists():
                try:
                    FAILED_REPOS_FILE.unlink()
                except Exception:
                    pass

            success_count, fail_count, failed_tasks = execute_parallel_clone(
                tasks,
                self.tasks,
                self.connections
            )

            if success_count > 0:
                successful_tasks = [task for task in tasks if task not in failed_tasks]
                check_success, check_fail, check_failed_tasks = check_repos_parallel(
                    successful_tasks,
                    parallel_tasks=self.tasks,
                    timeout=CHECK_TIMEOUT
                )

                if check_failed_tasks:
                    failed_tasks.extend(check_failed_tasks)
                    fail_count += len(check_failed_tasks)
                    success_count -= len(check_failed_tasks)

            if failed_tasks:
                save_failed_repos(
                    failed_tasks,
                    FAILED_REPOS_FILE,
                    config.REPO_OWNER or "qiao-925"
                )

            duration = int(time.time() - start_time)
            result = {
                "total": total_repos,
                "success": success_count,
                "fail": fail_count,
                "duration": duration,
                "failed_file": str(FAILED_REPOS_FILE) if failed_tasks else ""
            }
            self.finished.emit(True, result, "")

        except SystemExit:
            self.finished.emit(False, {}, "配置文件解析失败")
        except Exception as e:
            self.finished.emit(False, {}, str(e))
        finally:
            set_log_callback(prev_callback, log_to_stdout=prev_stdout, log_to_stderr=prev_stderr)


class CheckWorker(QThread):
    """仅检查工作线程"""
    finished = pyqtSignal(bool, dict, str)  # 成功标志, 结果, 错误信息
    log_signal = pyqtSignal(str)

    def __init__(self, config_file: str, tasks: int):
        super().__init__()
        self.config_file = config_file
        self.tasks = tasks

    def _log_callback(self, level: str, message: str, timestamp: str) -> None:
        self.log_signal.emit(f"[{level}] [{timestamp}] {message}")

    def run(self):
        prev_callback, prev_stdout, prev_stderr = get_log_state()
        set_log_callback(self._log_callback, log_to_stdout=False, log_to_stderr=False)

        try:
            start_time = time.time()
            tasks = parse_repo_groups(self.config_file)
            if not tasks:
                raise ValueError("未找到任何仓库任务")

            total_repos = len(tasks)

            success_count, fail_count, failed_tasks = check_repos_parallel(
                tasks,
                parallel_tasks=self.tasks,
                timeout=CHECK_TIMEOUT
            )

            if failed_tasks:
                save_failed_repos(
                    failed_tasks,
                    FAILED_REPOS_FILE,
                    config.REPO_OWNER or "qiao-925"
                )

            duration = int(time.time() - start_time)
            result = {
                "total": total_repos,
                "success": success_count,
                "fail": fail_count,
                "duration": duration,
                "failed_file": str(FAILED_REPOS_FILE) if failed_tasks else ""
            }
            self.finished.emit(True, result, "")

        except SystemExit:
            self.finished.emit(False, {}, "配置文件解析失败")
        except Exception as e:
            self.finished.emit(False, {}, str(e))
        finally:
            set_log_callback(prev_callback, log_to_stdout=prev_stdout, log_to_stderr=prev_stderr)

