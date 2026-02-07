# Main window UI

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QFormLayout, QFrame, QHBoxLayout, QInputDialog, QLabel,
    QLayout, QLineEdit, QListWidget, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QSizePolicy, QSpinBox, QTextEdit, QVBoxLayout, QWidget
)

if hasattr(Qt, "AA_EnableHighDpiScaling"):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
if hasattr(Qt, "AA_UseHighDpiPixmaps"):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

try:
    from qt_material import apply_stylesheet
    HAS_QT_MATERIAL = True
except Exception:
    HAS_QT_MATERIAL = False

from ..core import repo_config
from ..core.repo_config import read_owner, write_owner
from ..infra import ai, auth
from .chrome import apply_windows_dark_titlebar, build_app_icon, make_section_header
from .theme import CUSTOM_STYLESHEET
from .workers import (
    AiGenerateWorker, ApplyWorker, AuthWorker, CheckWorker, CloneWorker,
    ProfileWorker, SyncWorker
)

DEFAULT_TASKS = 5
DEFAULT_CONNECTIONS = 8
USE_CUSTOM_THEME = True
CONFIG_PATH = repo_config.SCRIPT_DIR / repo_config.CONFIG_FILE
FAILED_REPOS_FILE = repo_config.SCRIPT_DIR / "failed-repos.txt"
BACKUP_FILE_PREFIX = "REPO-GROUPS.backup"

class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.config_file = str(CONFIG_PATH)
        self.new_repos: List[str] = []
        self.sync_worker = None
        self.apply_worker = None
        self.clone_worker = None
        self.check_worker = None
        self.auth_worker = None
        self.profile_worker = None
        self.client_id = auth.load_client_id() or ""
        self.token, self.token_store = auth.load_token()
        self.login_name = auth.load_cached_login() if self.token else ""
        self.public_repo_count = -1
        self.profile_silent = False
        self.ai_generate_worker = None

        self.init_ui()
        self._update_auth_status()
        if self.token:
            self.refresh_profile(silent=True)
        if HAS_QT_MATERIAL and not USE_CUSTOM_THEME:
            try:
                apply_stylesheet(self.app, theme="light_teal.xml")
            except Exception:
                pass
        if USE_CUSTOM_THEME:
            self.apply_custom_theme()

    def apply_custom_theme(self):
        self.app.setStyleSheet(CUSTOM_STYLESHEET)

    @staticmethod
    def _make_section_header(title: str) -> QHBoxLayout:
        return make_section_header(title)

    def _ensure_repo_groups_file(self) -> bool:
        path = Path(self.config_file)
        if path.exists():
            if path.is_file():
                return True
            QMessageBox.warning(self, "错误", f"不是有效的文件: {path}")
            return False

        ok, error = repo_config.ensure_repo_groups_file(
            self.config_file,
            owner=self.login_name or "",
            keep_empty=True
        )
        if not ok:
            QMessageBox.warning(self, "错误", error)
            return False

        if hasattr(self, "log_text"):
            self.log(f"✅ 已生成配置文件: {self.config_file}")
        return True

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("GitHub 仓库管理工具")
        self.setMinimumSize(920, 880)
        self.setWindowIcon(build_app_icon())
        apply_windows_dark_titlebar(self)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(24, 24, 24, 24)
        central_widget.setLayout(main_layout)

        # 标题区域
        title_frame = QFrame()
        title_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        title_layout = QVBoxLayout()
        title_layout.setSizeConstraint(QLayout.SetMinimumSize)
        title_layout.setContentsMargins(0, 2, 0, 10)
        title_layout.setSpacing(4)
        title_frame.setLayout(title_layout)

        title_label = QLabel("GitHub 仓库管理工具")
        title_label.setAlignment(Qt.AlignHCenter)
        title_label.setObjectName("app-title")
        title_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        title_label.setMinimumHeight(32)
        title_layout.addWidget(title_label)

        subtitle_label = QLabel("同步 / 批量克隆 / 完整性检查")
        subtitle_label.setAlignment(Qt.AlignHCenter)
        subtitle_label.setObjectName("app-subtitle")
        subtitle_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        subtitle_label.setMinimumHeight(20)
        title_layout.addWidget(subtitle_label)

        main_layout.addWidget(title_frame)
        main_layout.addSpacing(6)

        # 授权登录（流程第一步）
        main_layout.addLayout(self._make_section_header("授权登录"))

        auth_layout = QHBoxLayout()
        auth_layout.setSpacing(10)
        self.auth_status_label = QLabel("登录状态：未登录")
        self.auth_status_label.setStyleSheet("font-size: 10pt;")
        auth_layout.addWidget(self.auth_status_label, 1)

        self.refresh_btn = QPushButton("刷新信息")
        self.refresh_btn.clicked.connect(self.refresh_profile)
        self.refresh_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        auth_layout.addWidget(self.refresh_btn)

        self.login_btn = QPushButton("登录 GitHub")
        self.login_btn.clicked.connect(self.start_login)
        self.login_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        auth_layout.addWidget(self.login_btn)

        self.logout_btn = QPushButton("退出登录")
        self.logout_btn.clicked.connect(self.logout)
        self.logout_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        auth_layout.addWidget(self.logout_btn)

        main_layout.addLayout(auth_layout)

        self.repo_count_label = QLabel("仓库统计：未获取")
        self.repo_count_label.setStyleSheet("font-size: 10pt;")
        main_layout.addWidget(self.repo_count_label)

        self.flow_hint_label = QLabel("流程：1 登录  2 分类（AI全量/增量 + 手动微调）  3 开始克隆")
        self.flow_hint_label.setStyleSheet("font-size: 9pt; color: #b0b0b0;")
        main_layout.addWidget(self.flow_hint_label)

        # 分类入口
        main_layout.addLayout(self._make_section_header("分类"))
        classify_layout = QHBoxLayout()
        classify_layout.setSpacing(10)

        self.ai_generate_btn = QPushButton("AI 自动分类（全量重建）")
        self.ai_generate_btn.clicked.connect(self.start_ai_generate)
        self.ai_generate_btn.setMinimumHeight(34)
        self.ai_generate_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.ai_generate_btn.setCursor(Qt.PointingHandCursor)
        classify_layout.addWidget(self.ai_generate_btn, 1)

        self.incremental_btn = QPushButton("增量更新到未分类（推荐）")
        self.incremental_btn.clicked.connect(self.start_incremental_update)
        self.incremental_btn.setMinimumHeight(34)
        self.incremental_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.incremental_btn.setCursor(Qt.PointingHandCursor)
        classify_layout.addWidget(self.incremental_btn, 1)

        self.open_file_btn = QPushButton("手动编辑")
        self.open_file_btn.clicked.connect(self.open_repo_groups_file)
        self.open_file_btn.setMinimumHeight(34)
        self.open_file_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.open_file_btn.setCursor(Qt.PointingHandCursor)
        classify_layout.addWidget(self.open_file_btn, 1)

        self.open_prompt_btn = QPushButton("编辑 AI Prompt")
        self.open_prompt_btn.clicked.connect(self.open_ai_prompt_file)
        self.open_prompt_btn.setMinimumHeight(34)
        self.open_prompt_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.open_prompt_btn.setCursor(Qt.PointingHandCursor)
        classify_layout.addWidget(self.open_prompt_btn, 1)

        main_layout.addLayout(classify_layout)

        classify_hint = QLabel("说明：AI 自动分类会重建分组；日常维护建议使用增量更新，再手动微调。")
        classify_hint.setStyleSheet("font-size: 9pt; color: #9a9a9a;")
        main_layout.addWidget(classify_hint)

        self.owner_label = QLabel("仓库所有者：未检测")
        self.owner_label.setStyleSheet("font-size: 10pt;")
        main_layout.addWidget(self.owner_label)

        # 参数设置
        main_layout.addLayout(self._make_section_header("并行参数"))

        params_frame = QFrame()
        params_layout = QFormLayout()
        params_layout.setLabelAlignment(Qt.AlignRight)
        params_layout.setFormAlignment(Qt.AlignLeft)
        params_layout.setHorizontalSpacing(16)
        params_layout.setVerticalSpacing(10)
        params_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        params_frame.setLayout(params_layout)

        self.tasks_spin = QSpinBox()
        self.tasks_spin.setRange(1, 64)
        self.tasks_spin.setValue(DEFAULT_TASKS)
        self.tasks_spin.setMinimumHeight(34)
        self.tasks_spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.connections_spin = QSpinBox()
        self.connections_spin.setRange(1, 64)
        self.connections_spin.setValue(DEFAULT_CONNECTIONS)
        self.connections_spin.setMinimumHeight(34)
        self.connections_spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        params_layout.addRow("并行任务数", self.tasks_spin)
        params_layout.addRow("并行连接数", self.connections_spin)
        main_layout.addWidget(params_frame)

        reset_params_layout = QHBoxLayout()
        reset_params_layout.addStretch(1)
        self.reset_params_btn = QPushButton("恢复默认参数")
        self.reset_params_btn.clicked.connect(self.reset_params)
        self.reset_params_btn.setMinimumHeight(30)
        reset_params_layout.addWidget(self.reset_params_btn)
        main_layout.addLayout(reset_params_layout)

        # 执行
        main_layout.addLayout(self._make_section_header("执行"))

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        self.clone_btn = QPushButton("开始克隆")
        self.clone_btn.clicked.connect(self.start_clone)
        self.clone_btn.setMinimumHeight(36)
        self.clone_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.clone_btn.setCursor(Qt.PointingHandCursor)
        actions_layout.addWidget(self.clone_btn, 1)

        main_layout.addLayout(actions_layout)

        run_hint = QLabel("说明：开始克隆会直接按当前 REPO-GROUPS.md 执行，无需先做增量更新。")
        run_hint.setStyleSheet("font-size: 9pt; color: #9a9a9a;")
        main_layout.addWidget(run_hint)

        failed_label = QLabel(f"失败列表：{FAILED_REPOS_FILE}（自动生成，可直接选择重试）")
        failed_label.setStyleSheet("font-size: 9pt; color: #aaa;")
        main_layout.addWidget(failed_label)

        # 进度条 + 状态
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("状态：就绪")
        self.status_label.setStyleSheet("font-size: 10pt; color: #bdbdbd;")
        main_layout.addWidget(self.status_label)

        # 增量更新结果
        main_layout.addLayout(self._make_section_header("增量更新结果"))

        self.repo_list = QListWidget()
        self.repo_list.setMinimumHeight(160)
        main_layout.addWidget(self.repo_list)

        self.stats_label = QLabel("新增仓库数: 0")
        self.stats_label.setStyleSheet("font-size: 11pt; font-weight: bold;")
        main_layout.addWidget(self.stats_label)

        # 日志区域
        main_layout.addLayout(self._make_section_header("操作日志"))

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(220)
        self.log_text.setMaximumHeight(320)
        main_layout.addWidget(self.log_text)

    def set_busy(self, busy: bool, status: str = ""):
        self.reset_params_btn.setEnabled(not busy)
        self.clone_btn.setEnabled(not busy)
        self.login_btn.setEnabled(not busy)
        self.refresh_btn.setEnabled(not busy and bool(self.token))
        self.logout_btn.setEnabled(not busy and bool(self.token))
        self.ai_generate_btn.setEnabled(not busy)
        self.incremental_btn.setEnabled(not busy and bool(self.token))
        self.open_file_btn.setEnabled(not busy)
        self.open_prompt_btn.setEnabled(not busy)
        self.progress_bar.setVisible(busy)
        if status:
            self.status_label.setText(status)

    def reset_params(self):
        self.tasks_spin.setValue(DEFAULT_TASKS)
        self.connections_spin.setValue(DEFAULT_CONNECTIONS)
        self.log("✅ 已恢复默认参数")

    def _update_auth_status(self):
        if self.token:
            login_text = f" ({self.login_name})" if self.login_name else ""
            self.auth_status_label.setText(f"登录状态：已登录{login_text} · 存储：{self.token_store}")
            self.logout_btn.setEnabled(True)
            self.login_btn.setText("重新登录")
            if self.public_repo_count >= 0:
                self.repo_count_label.setText(f"仓库统计：{self.public_repo_count} 个公共仓库")
            else:
                self.repo_count_label.setText("仓库统计：未获取")
            self._set_flow_hint("下一步：分类（AI全量/增量）并手动微调，然后开始克隆")
        else:
            self.auth_status_label.setText("登录状态：未登录")
            self.logout_btn.setEnabled(False)
            self.login_btn.setText("登录 GitHub")
            self.repo_count_label.setText("仓库统计：未获取")
            self._set_flow_hint("流程：1 登录  2 分类（AI全量/增量 + 手动微调）  3 开始克隆")
        if hasattr(self, "refresh_btn"):
            self.refresh_btn.setEnabled(bool(self.token))
        if hasattr(self, "incremental_btn"):
            self.incremental_btn.setEnabled(bool(self.token))

    def _set_flow_hint(self, text: str) -> None:
        if hasattr(self, "flow_hint_label"):
            self.flow_hint_label.setText(text)

    def refresh_profile(self, silent: bool = False):
        if not self.token:
            if not silent:
                QMessageBox.information(self, "提示", "请先登录 GitHub")
            return
        if self.profile_worker and self.profile_worker.isRunning():
            return

        self.profile_silent = silent
        self.set_busy(True, "状态：刷新账号信息中...")
        if not silent:
            self.log("🔄 正在刷新账号信息...")

        self.profile_worker = ProfileWorker(self.token)
        self.profile_worker.finished.connect(self.on_profile_finished)
        self.profile_worker.start()

    def on_profile_finished(self, success: bool, login: str, public_repos: int, error: str):
        self.set_busy(False, "状态：就绪")

        if not success:
            if not self.profile_silent:
                QMessageBox.warning(self, "⚠️ 获取失败", error)
            self.log(f"⚠️ 获取账号信息失败: {error}")
            self.profile_silent = False
            return

        if login:
            self.login_name = login
            auth.save_cached_login(login)
        if public_repos >= 0:
            self.public_repo_count = public_repos

        self._update_auth_status()
        if not self.profile_silent:
            self.log("✅ 账号信息已更新")
        self.profile_silent = False

    def start_login(self):
        if self.auth_worker and self.auth_worker.isRunning():
            return

        client_id = self.client_id or auth.load_client_id() or ""
        if not client_id:
            client_id, ok = QInputDialog.getText(
                self,
                "GitHub 授权",
                "请输入 GitHub OAuth App Client ID："
            )
            if not ok or not client_id.strip():
                return
            client_id = client_id.strip()
            auth.save_client_id(client_id)
            self.client_id = client_id

        self.set_busy(True, "状态：等待 GitHub 授权中...")
        self.log("🔐 开始 GitHub 授权（浏览器将自动打开）...")

        self.auth_worker = AuthWorker(client_id)
        self.auth_worker.code_ready.connect(self.on_auth_code_ready)
        self.auth_worker.finished.connect(self.on_auth_finished)
        self.auth_worker.start()

    def on_auth_code_ready(self, user_code: str, verification_url: str):
        try:
            QApplication.clipboard().setText(user_code)
        except Exception:
            pass

        message = f"已为你打开浏览器进行授权。\n\n验证码：{user_code}"
        if verification_url:
            message += f"\n授权地址：{verification_url}"
        message += "\n\n验证码已复制到剪贴板。"
        QMessageBox.information(self, "GitHub 授权", message)

    def on_auth_finished(self, success: bool, token: str, login: str, public_repos: int, error: str):
        self.set_busy(False, "状态：就绪")

        if not success:
            QMessageBox.critical(self, "❌ 授权失败", error)
            self.log(f"❌ 授权失败: {error}")
            return

        store = auth.save_token(token)
        self.token = token
        self.token_store = store
        self.login_name = login or self.login_name
        if public_repos is not None:
            self.public_repo_count = public_repos
        if login:
            auth.save_cached_login(login)

        self._update_auth_status()
        if error:
            QMessageBox.warning(self, "⚠️ 授权提示", error)
            self.log(f"⚠️ {error}")

        if login:
            if public_repos >= 0:
                self.log(f"✅ 授权成功，已登录账号: {login}（{public_repos} 个公共仓库）")
            else:
                self.log(f"✅ 授权成功，已登录账号: {login}")
        else:
            self.log("✅ 授权成功，已保存 Token")

    def logout(self):
        if not self.token:
            return
        auth.clear_token()
        self.token = None
        self.token_store = "none"
        self.login_name = ""
        self.public_repo_count = -1
        self._update_auth_status()
        self.log("✅ 已退出登录")

    def open_repo_groups_file(self):
        if not self._ensure_repo_groups_file():
            return
        path = Path(self.config_file)
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except Exception:
            QMessageBox.information(self, "提示", f"请手动打开文件：{path}")

    def open_ai_prompt_file(self):
        prompt_path = ai.get_classify_prompt_path()
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        if not prompt_path.exists():
            ai.build_classify_system_prompt([])

        try:
            if sys.platform == "win32":
                os.startfile(str(prompt_path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(prompt_path)], check=False)
            else:
                subprocess.run(["xdg-open", str(prompt_path)], check=False)
        except Exception:
            QMessageBox.information(self, "提示", f"请手动打开文件：{prompt_path}")

    def _has_existing_classification(self) -> bool:
        config_path = Path(self.config_file)
        if not config_path.exists() or not config_path.is_file():
            return False

        try:
            content, _, _, _ = repo_config.read_text_preserve_encoding(config_path)
        except Exception:
            return False

        for line in content.splitlines():
            if line.lstrip().startswith("- "):
                return True
        return False

    def _backup_repo_groups_file(self) -> Tuple[Path, str]:
        source = Path(self.config_file)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = source.parent / f"{BACKUP_FILE_PREFIX}-{timestamp}.md"
        try:
            shutil.copy2(source, backup)
            return backup, ""
        except Exception as exc:
            return backup, str(exc)

    def start_ai_generate(self):
        if not self.token:
            QMessageBox.information(self, "提示", "请先登录 GitHub")
            return
        if not self._ensure_repo_groups_file():
            return

        owner = self.login_name
        if not owner:
            ok, file_owner, _ = read_owner(self.config_file)
            if ok:
                owner = file_owner
        if not owner:
            owner, ok = QInputDialog.getText(self, "仓库所有者", "请输入仓库所有者：")
            if not ok or not owner.strip():
                return
            owner = owner.strip()

        if self._has_existing_classification():
            overwrite_reply = QMessageBox.question(
                self,
                "⚠️ 全量覆盖确认",
                "检测到 REPO-GROUPS.md 已存在分类内容。\n"
                "继续将执行全量重建，并覆盖现有分类结果。\n\n"
                "是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if overwrite_reply != QMessageBox.Yes:
                return

            backup_path, backup_error = self._backup_repo_groups_file()
            if backup_error:
                continue_reply = QMessageBox.question(
                    self,
                    "备份失败",
                    f"自动备份失败：{backup_error}\n\n是否仍继续覆盖？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if continue_reply != QMessageBox.Yes:
                    return
            else:
                self.log(f"🗂️ 已备份现有分类文件：{backup_path}")

        api_key, _ = ai.load_api_key()
        if not api_key:
            api_key, ok = QInputDialog.getText(
                self,
                "AI 分类",
                "请输入 DeepSeek API Key：",
                QLineEdit.Password
            )
            if not ok or not api_key.strip():
                return
            ai.save_api_key(api_key.strip())
            api_key = api_key.strip()

        groups, tags = repo_config.load_groups_from_file(self.config_file)

        base_url, model = ai.load_ai_config()

        self.set_busy(True, "状态：AI 自动分类中...")
        self.log("🤖 开始 AI 自动分类（生成 REPO-GROUPS.md）...")

        self.ai_generate_worker = AiGenerateWorker(
            owner,
            self.token,
            self.config_file,
            groups,
            tags,
            api_key,
            base_url,
            model
        )
        self.ai_generate_worker.progress.connect(self.on_ai_generate_progress)
        self.ai_generate_worker.finished.connect(self.on_ai_generate_finished)
        self.ai_generate_worker.start()

    def on_ai_generate_progress(self, current: int, total: int):
        self.status_label.setText(f"状态：AI 自动分类中... ({current}/{total})")

    def on_ai_generate_finished(self, success: bool, total: int, error: str):
        self.set_busy(False, "状态：就绪")
        if not success:
            QMessageBox.critical(self, "AI 分类失败", error)
            self.log(f"❌ AI 分类失败: {error}")
            return

        self.log(f"✅ AI 分类完成，共 {total} 个仓库")
        QMessageBox.information(self, "完成", "AI 分类已写入 REPO-GROUPS.md，可直接手动微调")
        self._refresh_owner_label()
        self._set_flow_hint("下一步：手动微调分类文件，然后开始克隆")
        self.open_repo_groups_file()

    def _resolve_owner_for_sync(self) -> str:
        if not self.login_name:
            return ""

        ok, file_owner, error = read_owner(self.config_file)
        if ok:
            if file_owner != self.login_name:
                reply = QMessageBox.question(
                    self,
                    "⚠️ 仓库所有者不一致",
                    f"配置文件 owner 为 {file_owner}\n登录账号为 {self.login_name}\n\n是否使用登录账号进行同步？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    update_reply = QMessageBox.question(
                        self,
                        "更新配置文件",
                        "是否将登录账号写入 REPO-GROUPS.md 作为仓库所有者？",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    if update_reply == QMessageBox.Yes:
                        success, write_error = write_owner(self.config_file, self.login_name)
                        if not success:
                            QMessageBox.warning(self, "写入失败", write_error)
                    return self.login_name
                return ""
            return ""

        # 文件缺少 owner，默认使用登录账号
        reply = QMessageBox.question(
            self,
            "缺少仓库所有者",
            f"配置文件未找到仓库所有者信息。\n是否使用登录账号 {self.login_name} 进行同步？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return ""

        write_reply = QMessageBox.question(
            self,
            "写入配置文件",
            "是否将登录账号写入 REPO-GROUPS.md 作为仓库所有者？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if write_reply == QMessageBox.Yes:
            success, write_error = write_owner(self.config_file, self.login_name)
            if not success:
                QMessageBox.warning(self, "写入失败", write_error)
        return self.login_name

    def start_incremental_update(self):
        if not self.token:
            QMessageBox.information(self, "提示", "请先登录 GitHub")
            return
        if not self._ensure_repo_groups_file():
            return

        self.set_busy(True, "状态：增量更新中（拉取新增仓库）...")
        self.repo_list.clear()
        self.new_repos = []
        self.stats_label.setText("新增仓库数: 0")

        self.log("🔄 开始增量更新：拉取新增仓库...")

        owner_override = self._resolve_owner_for_sync()

        self.sync_worker = SyncWorker(
            self.config_file,
            owner_override=owner_override,
            token=self.token or ""
        )
        self.sync_worker.finished.connect(self.on_incremental_preview_finished)
        self.sync_worker.start()

    def on_incremental_preview_finished(self, success: bool, owner: str, new_repos: List[str], error: str):
        self.set_busy(False, "状态：就绪")

        if not success:
            QMessageBox.critical(self, "❌ 错误", f"增量更新失败:\n{error}")
            self.log(f"❌ 错误: {error}")
            return

        self.owner_label.setText(f"仓库所有者：{owner}")
        self.new_repos = new_repos

        if new_repos:
            self.repo_list.addItems(new_repos)
            self.stats_label.setText(f"新增仓库数: {len(new_repos)}")
            self.log(f"✅ 发现 {len(new_repos)} 个新增仓库，准备写入“未分类”")
            self.set_busy(True, "状态：增量更新中（写入未分类）...")
            self.apply_worker = ApplyWorker(self.config_file, self.new_repos)
            self.apply_worker.finished.connect(self.on_incremental_apply_finished)
            self.apply_worker.start()
        else:
            self.stats_label.setText("新增仓库数: 0")
            self.log("ℹ️ 没有新增仓库，REPO-GROUPS.md 已是最新")
            QMessageBox.information(self, "ℹ️ 提示", "没有新增仓库，REPO-GROUPS.md 已是最新")
            self._set_flow_hint("下一步：可直接开始克隆")

    def on_incremental_apply_finished(self, success: bool, error: str):
        self.set_busy(False, "状态：就绪")

        if not success:
            QMessageBox.critical(self, "❌ 错误", f"写入未分类失败:\n{error}")
            self.log(f"❌ 错误: {error}")
            return

        QMessageBox.information(
            self,
            "✅ 成功",
            f"增量更新完成：已写入 {len(self.new_repos)} 个仓库到\"未分类\"分组。\n"
            "建议先手动微调分类，再开始克隆。"
        )
        self.log(f"✅ 增量更新完成，成功写入 {len(self.new_repos)} 个仓库")
        self._set_flow_hint("下一步：手动微调分类文件，然后开始克隆")
        self.open_repo_groups_file()

    def start_clone(self):
        if not self._ensure_repo_groups_file():
            return

        self.set_busy(True, "状态：克隆中...")
        self.log("🚀 开始批量克隆...")

        self.clone_worker = CloneWorker(
            self.config_file,
            self.tasks_spin.value(),
            self.connections_spin.value()
        )
        self.clone_worker.log_signal.connect(self.log)
        self.clone_worker.finished.connect(self.on_clone_finished)
        self.clone_worker.start()

    def on_clone_finished(self, success: bool, result: Dict[str, int], error: str):
        self.set_busy(False, "状态：就绪")

        if not success:
            QMessageBox.critical(self, "❌ 错误", f"克隆失败:\n{error}")
            self.log(f"❌ 错误: {error}")
            return

        self._refresh_owner_label()
        summary = self._format_summary("克隆完成", result)
        self.status_label.setText(f"状态：{summary}")
        self.log(f"✅ {summary}")

        if result.get("fail", 0) > 0:
            QMessageBox.warning(
                self,
                "⚠️ 部分失败",
                f"失败 {result.get('fail', 0)} 个仓库，失败列表已生成：\n{FAILED_REPOS_FILE}"
            )

    def start_check(self):
        if not self._ensure_repo_groups_file():
            return

        self.set_busy(True, "状态：检查中...")
        self.log("🧪 开始完整性检查...")

        self.check_worker = CheckWorker(
            self.config_file,
            self.tasks_spin.value()
        )
        self.check_worker.log_signal.connect(self.log)
        self.check_worker.finished.connect(self.on_check_finished)
        self.check_worker.start()

    def on_check_finished(self, success: bool, result: Dict[str, int], error: str):
        self.set_busy(False, "状态：就绪")

        if not success:
            QMessageBox.critical(self, "❌ 错误", f"检查失败:\n{error}")
            self.log(f"❌ 错误: {error}")
            return

        self._refresh_owner_label()
        summary = self._format_summary("检查完成", result)
        self.status_label.setText(f"状态：{summary}")
        self.log(f"✅ {summary}")

        if result.get("fail", 0) > 0:
            QMessageBox.warning(
                self,
                "⚠️ 部分失败",
                f"失败 {result.get('fail', 0)} 个仓库，失败列表已生成：\n{FAILED_REPOS_FILE}"
            )

    def _format_summary(self, prefix: str, result: Dict[str, int]) -> str:
        total = result.get("total", 0)
        success = result.get("success", 0)
        fail = result.get("fail", 0)
        duration = result.get("duration", 0)
        return f"{prefix}：总数 {total}，成功 {success}，失败 {fail}，耗时 {self._format_duration(duration)}"

    def _refresh_owner_label(self):
        if repo_config.REPO_OWNER:
            self.owner_label.setText(f"仓库所有者：{repo_config.REPO_OWNER}")

    @staticmethod
    def _format_duration(seconds: int) -> str:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours}小时 {minutes}分钟 {secs}秒"
        if minutes > 0:
            return f"{minutes}分钟 {secs}秒"
        return f"{secs}秒"

    def log(self, message: str):
        self.log_text.append(message)



def main():
    app = QApplication(sys.argv)
    window = MainWindow(app)
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
