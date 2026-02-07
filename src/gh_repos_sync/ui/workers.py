# GUI workers (threaded tasks)

from typing import Dict, List

from PyQt5.QtCore import QThread, pyqtSignal

from ..application.ai_generation import generate_repo_groups_with_ai
from ..application.execution import run_clone_and_check, run_pull_updates
from ..core.repo_config import apply_sync, preview_sync
from ..infra import ai, auth
from ..infra.github_api import fetch_public_repos
from ..infra.logger import get_log_state, set_log_callback


def _format_progress_message(
    phase: str,
    done: int,
    total: int,
    success: int,
    fail: int,
) -> str:
    phase_label = {
        "clone": "克隆",
        "check": "完整性检查",
        "pull": "批量更新",
    }.get(phase, phase)
    return f"[{phase_label}] 进度 {done}/{total}，成功 {success}，失败 {fail}"


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
            token=self.token or None,
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
            data.get("expires_in", 900),
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
        success, repos, error = fetch_public_repos(self.owner, token=self.token or None)
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
            progress_cb=_progress,
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
        model: str,
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
        def _progress(done: int, total: int) -> None:
            self.progress.emit(done, total)

        success, total, error = generate_repo_groups_with_ai(
            self.owner,
            self.token,
            self.config_file,
            self.groups,
            self.tags,
            self.api_key,
            self.base_url,
            self.model,
            progress_cb=_progress,
        )
        self.finished.emit(success, total, error)


class CloneWorker(QThread):
    """克隆 + 完整性检查工作线程"""

    finished = pyqtSignal(bool, dict, str)  # 成功标志, 结果, 错误信息
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(str, int, int, int, int)

    def __init__(self, config_file: str, tasks: int, connections: int):
        super().__init__()
        self.config_file = config_file
        self.tasks = tasks
        self.connections = connections

    def _log_callback(self, level: str, message: str, timestamp: str) -> None:
        self.log_signal.emit(f"[{level}] [{timestamp}] {message}")

    def _progress_callback(self, phase: str, done: int, total: int, success: int, fail: int) -> None:
        self.progress_signal.emit(phase, done, total, success, fail)
        self.log_signal.emit(_format_progress_message(phase, done, total, success, fail))

    def run(self):
        prev_callback, prev_stdout, prev_stderr = get_log_state()
        set_log_callback(self._log_callback, log_to_stdout=False, log_to_stderr=False)

        try:
            success, result, error = run_clone_and_check(
                self.config_file,
                tasks=self.tasks,
                connections=self.connections,
                progress_cb=self._progress_callback,
            )
            self.finished.emit(success, result, error)
        finally:
            set_log_callback(prev_callback, log_to_stdout=prev_stdout, log_to_stderr=prev_stderr)


class PullWorker(QThread):
    """批量更新工作线程"""

    finished = pyqtSignal(bool, dict, str)  # 成功标志, 结果, 错误信息
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(str, int, int, int, int)

    def __init__(self, config_file: str, tasks: int):
        super().__init__()
        self.config_file = config_file
        self.tasks = tasks

    def _log_callback(self, level: str, message: str, timestamp: str) -> None:
        self.log_signal.emit(f"[{level}] [{timestamp}] {message}")

    def _progress_callback(self, phase: str, done: int, total: int, success: int, fail: int) -> None:
        self.progress_signal.emit(phase, done, total, success, fail)
        self.log_signal.emit(_format_progress_message(phase, done, total, success, fail))

    def run(self):
        prev_callback, prev_stdout, prev_stderr = get_log_state()
        set_log_callback(self._log_callback, log_to_stdout=False, log_to_stderr=False)

        try:
            success, result, error = run_pull_updates(
                self.config_file,
                tasks=self.tasks,
                progress_cb=self._progress_callback,
            )
            self.finished.emit(success, result, error)
        finally:
            set_log_callback(prev_callback, log_to_stdout=prev_stdout, log_to_stderr=prev_stderr)

