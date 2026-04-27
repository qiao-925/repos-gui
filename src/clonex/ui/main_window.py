# Main window UI

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QFormLayout, QFrame, QHBoxLayout, QInputDialog, QLabel,
    QLayout, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QSizePolicy, QSpinBox, QVBoxLayout,
    QWidget
)
from PyQt6.QtGui import QShortcut

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
from ..core.process_control import request_shutdown
from ..core.repo_config import read_owner, write_owner
from ..infra import auth
from ..infra.auto_gist_sync import get_auto_gist_sync
from ..infra.logger import get_log_file_path
from .chrome import apply_windows_dark_titlebar, build_app_icon, make_section_header
from .advanced_settings_dialog import AdvancedSettingsDialog
from .theme import build_custom_stylesheet
from .workers import (
    ApplyWorker, AuthWorker, CloneWorker, LocalGenerateWorker,
    ProfileWorker, PullWorker, SyncWorker,
)

DEFAULT_UI_SCALE = 1.0
DEFAULT_TASKS = 5
DEFAULT_CONNECTIONS = 8
MIN_UI_SCALE = 0.80
MAX_UI_SCALE = 1.30
UI_SCALE_STEP = 0.05
USE_CUSTOM_THEME = True
CONFIG_PATH = repo_config.SCRIPT_DIR / repo_config.CONFIG_FILE
FAILED_REPOS_FILE = repo_config.SCRIPT_DIR / "failed-repos.txt"
BACKUP_FILE_PREFIX = "REPO-GROUPS.backup"
LEGACY_DIST_DIR = repo_config.SCRIPT_DIR / "dist"
LEGACY_CONFIG_PATH = LEGACY_DIST_DIR / repo_config.CONFIG_FILE
LEGACY_FAILED_REPOS_PATH = LEGACY_DIST_DIR / "failed-repos.txt"

class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.startup_notices: List[str] = []
        self._migrate_legacy_runtime_files()
        self.config_file = str(CONFIG_PATH)
        self.new_repos: List[str] = []
        self.sync_worker = None
        self.apply_worker = None
        self.clone_worker = None
        self.pull_worker = None
        self.auth_worker = None
        self.profile_worker = None
        self.client_id = auth.load_client_id() or ""
        self.token, self.token_store = auth.load_token()
        self.login_name = auth.load_cached_login() if self.token else ""
        self.public_repo_count = -1
        self.profile_silent = False
        self.local_generate_worker = None
        self.parallel_tasks = DEFAULT_TASKS
        self.parallel_connections = DEFAULT_CONNECTIONS
        self.ui_scale = DEFAULT_UI_SCALE
        self.current_execution_label = "克隆"
        self.startup_notices.append(f"详细日志文件：{get_log_file_path()}")
        
        # 初始化自动 Gist 同步
        self.auto_gist_sync = get_auto_gist_sync(self.config_file)

        self.init_ui()
        self._setup_zoom_shortcuts()
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
        self._apply_ui_metrics()
        for notice in self.startup_notices:
            self.log(notice)

    def _migrate_legacy_runtime_files(self) -> None:
        migrations = [
            (LEGACY_CONFIG_PATH, CONFIG_PATH, "配置文件"),
            (LEGACY_FAILED_REPOS_PATH, FAILED_REPOS_FILE, "失败列表"),
        ]

        for source, target, label in migrations:
            if not source.exists() or not source.is_file() or target.exists():
                continue

            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))
                self.startup_notices.append(f"♻️ 已迁移{label}：{source} -> {target}")
            except Exception as exc:
                self.startup_notices.append(f"⚠️ 迁移{label}失败：{exc}")

    def apply_custom_theme(self):
        self.app.setStyleSheet(build_custom_stylesheet(self.ui_scale))

    @staticmethod
    def _clamp_ui_scale(scale: float) -> float:
        return max(MIN_UI_SCALE, min(MAX_UI_SCALE, scale))

    def _scaled(self, value: int) -> int:
        return max(1, int(round(value * self.ui_scale)))

    def _setup_zoom_shortcuts(self) -> None:
        self.zoom_in_shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.ZoomIn), self)
        self.zoom_out_shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.ZoomOut), self)
        self.zoom_reset_shortcut = QShortcut(QKeySequence("Ctrl+0"), self)
        self.zoom_in_shortcut_alt = QShortcut(QKeySequence("Ctrl+="), self)

        self.zoom_in_shortcut.activated.connect(lambda: self.adjust_ui_scale(UI_SCALE_STEP))
        self.zoom_in_shortcut_alt.activated.connect(lambda: self.adjust_ui_scale(UI_SCALE_STEP))
        self.zoom_out_shortcut.activated.connect(lambda: self.adjust_ui_scale(-UI_SCALE_STEP))
        self.zoom_reset_shortcut.activated.connect(self.reset_ui_scale)

    def adjust_ui_scale(self, delta: float) -> None:
        target_scale = self._clamp_ui_scale(round(self.ui_scale + delta, 2))
        if target_scale == self.ui_scale:
            return
        self.ui_scale = target_scale
        if USE_CUSTOM_THEME:
            self.apply_custom_theme()
        self._apply_ui_metrics()
        self.log(f"界面缩放：{int(round(self.ui_scale * 100))}%")

    def reset_ui_scale(self) -> None:
        if self.ui_scale == DEFAULT_UI_SCALE:
            return
        self.ui_scale = DEFAULT_UI_SCALE
        if USE_CUSTOM_THEME:
            self.apply_custom_theme()
        self._apply_ui_metrics()
        self.log("界面缩放：100%")

    def _apply_ui_metrics(self) -> None:
        self.setMinimumSize(self._scaled(800), self._scaled(780))
        self.main_layout.setSpacing(self._scaled(8))
        self.main_layout.setContentsMargins(
            self._scaled(18), self._scaled(18), self._scaled(18), self._scaled(18)
        )

        self.title_layout.setContentsMargins(0, self._scaled(2), 0, self._scaled(8))
        self.title_layout.setSpacing(self._scaled(3))
        self.title_label.setMinimumHeight(self._scaled(28))
        self.subtitle_label.setMinimumHeight(self._scaled(18))

        self.auth_layout.setSpacing(self._scaled(8))
        self.classify_layout.setSpacing(self._scaled(8))
        self.actions_layout.setSpacing(self._scaled(8))

        self.incremental_btn.setMinimumHeight(self._scaled(30))
        self.local_generate_btn.setMinimumHeight(self._scaled(30))
        self.open_file_btn.setMinimumHeight(self._scaled(30))

        self.log_panel_layout.setSpacing(self._scaled(8))
        self.log_panel_layout.setContentsMargins(
            self._scaled(12), self._scaled(12), self._scaled(12), self._scaled(12)
        )
        self.log_toolbar_layout.setSpacing(self._scaled(8))
        self.open_log_btn.setMinimumHeight(self._scaled(28))
        self.clear_log_btn.setMinimumHeight(self._scaled(28))
        self.log_text.setMinimumHeight(self._scaled(320))
        self.log_text.setMaximumHeight(16777215)

    def closeEvent(self, event) -> None:
        self.set_busy(True, "状态：正在关闭并终止后台任务...")
        request_shutdown()

        if self.clone_worker and self.clone_worker.isRunning():
            self.clone_worker.wait(2000)
        if self.pull_worker and self.pull_worker.isRunning():
            self.pull_worker.wait(2000)

        super().closeEvent(event)

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
        self.setWindowTitle("CloneX - GitHub 仓库管理工具")
        self.setMinimumSize(800, 780)
        self.setWindowIcon(build_app_icon())
        apply_windows_dark_titlebar(self)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(24, 24, 24, 24)
        central_widget.setLayout(self.main_layout)

        # 标题区域
        title_frame = QFrame()
        title_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.title_layout = QVBoxLayout()
        self.title_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.title_layout.setContentsMargins(0, 2, 0, 10)
        self.title_layout.setSpacing(4)
        title_frame.setLayout(self.title_layout)

        self.title_label = QLabel("CloneX")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.title_label.setObjectName("app-title")
        self.title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.title_label.setMinimumHeight(32)
        self.title_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("同步 / 批量克隆 / 完整性检查")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.subtitle_label.setObjectName("app-subtitle")
        self.subtitle_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.subtitle_label.setMinimumHeight(20)
        self.title_layout.addWidget(self.subtitle_label)

        self.main_layout.addWidget(title_frame)
        self.main_layout.addSpacing(6)

        # 授权登录（流程第一步）
        self.main_layout.addLayout(self._make_section_header("授权登录"))

        self.auth_layout = QHBoxLayout()
        self.auth_layout.setSpacing(10)
        self.auth_status_label = QLabel("登录状态：未登录")
        self.auth_status_label.setStyleSheet("font-size: 10pt;")
        self.auth_layout.addWidget(self.auth_status_label, 1)

        self.refresh_btn = QPushButton("刷新信息")
        self.refresh_btn.clicked.connect(self.refresh_profile)
        self.refresh_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.auth_layout.addWidget(self.refresh_btn)

        self.login_btn = QPushButton("登录 GitHub")
        self.login_btn.clicked.connect(self.start_login)
        self.login_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.auth_layout.addWidget(self.login_btn)

        self.logout_btn = QPushButton("退出登录")
        self.logout_btn.clicked.connect(self.logout)
        self.logout_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.auth_layout.addWidget(self.logout_btn)

        self.main_layout.addLayout(self.auth_layout)

        self.repo_count_label = QLabel("仓库统计：未获取")
        self.repo_count_label.setStyleSheet("font-size: 10pt;")
        self.main_layout.addWidget(self.repo_count_label)

        self.flow_hint_label = QLabel("流程：1 登录  2 整理（拉取/基础分类）  3 手动微调  4 开始执行")
        self.flow_hint_label.setStyleSheet("font-size: 9pt; color: #b0b0b0;")
        self.main_layout.addWidget(self.flow_hint_label)

        self.zoom_hint_label = QLabel("缩放快捷键：Ctrl + / Ctrl - / Ctrl 0")
        self.zoom_hint_label.setStyleSheet("font-size: 9pt; color: #8d8d8d;")
        self.main_layout.addWidget(self.zoom_hint_label)

        # 整理与同步入口 (原分类)
        self.main_layout.addLayout(self._make_section_header("整理与同步"))
        self.classify_layout = QHBoxLayout()
        self.classify_layout.setSpacing(10)

        self.incremental_btn = QPushButton("拉取新仓库 (增量到未分类)")
        self.incremental_btn.clicked.connect(self.start_incremental_update)
        self.incremental_btn.setMinimumHeight(34)
        self.incremental_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.incremental_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.classify_layout.addWidget(self.incremental_btn, 1)

        self.local_generate_btn = QPushButton("自动分类 (按语言)")
        self.local_generate_btn.clicked.connect(self.start_local_generate)
        self.local_generate_btn.setMinimumHeight(34)
        self.local_generate_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.local_generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.classify_layout.addWidget(self.local_generate_btn, 1)

        self.open_file_btn = QPushButton("手动编辑分组")
        self.open_file_btn.clicked.connect(self.open_repo_groups_file)
        self.open_file_btn.setMinimumHeight(34)
        self.open_file_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.open_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.classify_layout.addWidget(self.open_file_btn, 1)

        self.advanced_btn = QPushButton("⚙️ 高级设置...")
        self.advanced_btn.clicked.connect(self.open_advanced_settings)
        self.advanced_btn.setMinimumHeight(34)
        self.advanced_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.advanced_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.classify_layout.addWidget(self.advanced_btn, 1)

        self.main_layout.addLayout(self.classify_layout)

        classify_hint = QLabel("说明：按语言自动分类会覆盖未分类仓库；高级设置内包含 AI 分类、云端同步和并发控制。")
        classify_hint.setStyleSheet("font-size: 9pt; color: #9a9a9a;")
        self.main_layout.addWidget(classify_hint)

        self.owner_label = QLabel("仓库所有者：未检测")
        self.owner_label.setStyleSheet("font-size: 10pt;")
        self.main_layout.addWidget(self.owner_label)

        # 执行
        self.main_layout.addLayout(self._make_section_header("执行"))

        self.actions_layout = QHBoxLayout()
        self.actions_layout.setSpacing(10)

        self.clone_btn = QPushButton("开始克隆")
        self.clone_btn.clicked.connect(self.start_clone)
        self.clone_btn.setMinimumHeight(36)
        self.clone_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.clone_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.actions_layout.addWidget(self.clone_btn, 1)

        self.pull_btn = QPushButton("批量更新已克隆仓库")
        self.pull_btn.clicked.connect(self.start_pull)
        self.pull_btn.setMinimumHeight(36)
        self.pull_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.pull_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.actions_layout.addWidget(self.pull_btn, 1)

        self.retry_failed_btn = QPushButton("一键重试失败仓库")
        self.retry_failed_btn.clicked.connect(self.retry_failed_repos)
        self.retry_failed_btn.setMinimumHeight(36)
        self.retry_failed_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.retry_failed_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.actions_layout.addWidget(self.retry_failed_btn, 1)

        self.main_layout.addLayout(self.actions_layout)

        run_hint = QLabel("说明：克隆/更新都按当前 REPO-GROUPS.md 执行；失败仓库会写入 failed-repos.txt 可一键重试。")
        run_hint.setStyleSheet("font-size: 9pt; color: #9a9a9a;")
        self.main_layout.addWidget(run_hint)

        failed_label = QLabel(f"失败列表：{FAILED_REPOS_FILE}")
        failed_label.setStyleSheet("font-size: 9pt; color: #aaa;")
        self.main_layout.addWidget(failed_label)

        # 进度条 + 状态
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.main_layout.addWidget(self.progress_bar)

        self.progress_detail_label = QLabel("进度：-/-，成功 0，失败 0")
        self.progress_detail_label.setStyleSheet("font-size: 9pt; color: #9f9f9f;")
        self.progress_detail_label.setVisible(False)
        self.main_layout.addWidget(self.progress_detail_label)

        self.status_label = QLabel("状态：就绪")
        self.status_label.setStyleSheet("font-size: 10pt; color: #bdbdbd;")
        self.main_layout.addWidget(self.status_label)

        # 日志区域（包含增量更新结果）
        self.main_layout.addLayout(self._make_section_header("操作日志"))

        self.log_panel = QFrame()
        self.log_panel.setObjectName("log-panel")
        self.log_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.log_panel_layout = QVBoxLayout()
        self.log_panel_layout.setContentsMargins(12, 12, 12, 12)
        self.log_panel_layout.setSpacing(8)
        self.log_panel.setLayout(self.log_panel_layout)

        self.log_toolbar_layout = QHBoxLayout()
        self.log_toolbar_layout.setSpacing(8)

        self.log_hint_label = QLabel("按时间顺序逐行显示，最新日志默认追加到底部。")
        self.log_hint_label.setObjectName("log-hint")
        self.log_toolbar_layout.addWidget(self.log_hint_label, 1)

        self.open_log_btn = QPushButton("打开日志文件")
        self.open_log_btn.setObjectName("log-action")
        self.open_log_btn.clicked.connect(self.open_log_file)
        self.log_toolbar_layout.addWidget(self.open_log_btn)

        self.clear_log_btn = QPushButton("清空面板")
        self.clear_log_btn.setObjectName("log-action")
        self.clear_log_btn.clicked.connect(self.clear_log_panel)
        self.log_toolbar_layout.addWidget(self.clear_log_btn)

        self.log_panel_layout.addLayout(self.log_toolbar_layout)

        self.log_text = QPlainTextEdit()
        self.log_text.setObjectName("log-view")
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.log_text.setUndoRedoEnabled(False)
        self.log_text.setCenterOnScroll(False)
        self.log_text.setPlaceholderText("运行日志会显示在这里。")
        self.log_text.document().setMaximumBlockCount(3000)
        self.log_text.setMinimumHeight(320)
        self.log_text.setMaximumHeight(16777215)
        self.log_panel_layout.addWidget(self.log_text, 1)
        self.main_layout.addWidget(self.log_panel, 1)

    def set_busy(self, busy: bool, status: str = ""):
        self.clone_btn.setEnabled(not busy)
        self.pull_btn.setEnabled(not busy)
        self.retry_failed_btn.setEnabled(not busy)
        self.login_btn.setEnabled(not busy)
        self.incremental_btn.setEnabled(not busy)
        self.local_generate_btn.setEnabled(not busy)
        self.open_file_btn.setEnabled(not busy)
        self.advanced_btn.setEnabled(not busy)
        self.refresh_btn.setEnabled(not busy and bool(self.token))
        self.logout_btn.setEnabled(not busy and bool(self.token))

        self.progress_bar.setVisible(busy)
        self.progress_detail_label.setVisible(busy)
        if not busy:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_detail_label.setText("进度：-/-，成功 0，失败 0")
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
                self.repo_count_label.setText(f"仓库统计：{self.public_repo_count} 个公共仓库（已自动启用 private 访问）")
            else:
                self.repo_count_label.setText("仓库统计：未获取")
            self._set_flow_hint("下一步：使用整理功能拉取仓库并微调，然后开始执行")
        else:
            self.auth_status_label.setText("登录状态：未登录")
            self.logout_btn.setEnabled(False)
            self.login_btn.setText("登录 GitHub")
            self.repo_count_label.setText("仓库统计：未获取")
            self._set_flow_hint("流程：1 登录（自动包含 private）  2 整理（拉取 + 自动/手动分类）  3 开始克隆")
        if hasattr(self, "refresh_btn"):
            self.refresh_btn.setEnabled(bool(self.token))
        if hasattr(self, "incremental_btn"):
            self.incremental_btn.setEnabled(True)

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

        # 更新自动同步实例
        self.update_auto_sync_token(token)
        
        # 登录成功后自动初始化 Gist 同步（无感发现或准备创建）
        self.auto_gist_sync.auto_init_sync(token)

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
        self._open_local_path(Path(self.config_file))

    def open_gist_manager(self):
        """Open Gist configuration manager dialog."""
        dialog = GistManagerDialog(self)
        dialog.exec()

    def open_auto_sync_settings(self):
        """Open auto sync settings dialog."""
        dialog = AutoSyncDialog(self, self.auto_gist_sync)
        dialog.sync_requested.connect(self.handle_sync_request)
        dialog.exec()

    def handle_sync_request(self, action: str, description: str):
        """Handle manual sync request from auto sync dialog."""
        if action == "upload":
            self.sync_config_to_gist_now()
        elif action == "download":
            self.sync_config_from_gist_now()

    def enable_auto_gist_sync(self, gist_id: str):
        """Enable automatic Gist synchronization."""
        if not self.token:
            QMessageBox.warning(self, "警告", "需要登录 GitHub 才能启用自动同步")
            return
        
        success, message = self.auto_gist_sync.enable_auto_sync(
            gist_id, 
            auto_upload=True, 
            auto_download=True
        )
        
        if success:
            QMessageBox.information(self, "成功", message)
            self.log(f"🔄 {message}")
        else:
            QMessageBox.warning(self, "错误", message)
            self.log(f"❌ 启用自动同步失败: {message}")

    def disable_auto_gist_sync(self):
        """Disable automatic Gist synchronization."""
        self.auto_gist_sync.disable_auto_sync()
        QMessageBox.information(self, "成功", "已禁用自动同步")
        self.log("🔄 已禁用自动同步")

    def get_auto_sync_status(self):
        """Get current auto-sync status."""
        status = self.auto_gist_sync.get_status()
        
        status_text = "自动同步状态:\n\n"
        status_text += f"启用状态: {'✅ 已启用' if status['enabled'] else '❌ 未启用'}\n"
        status_text += f"Gist ID: {status['gist_id'] or '未配置'}\n"
        status_text += f"自动上传: {'✅' if status['auto_upload'] else '❌'}\n"
        status_text += f"自动下载: {'✅' if status['auto_download'] else '❌'}\n"
        
        if status['last_sync'] > 0:
            from datetime import datetime
            last_sync_time = datetime.fromtimestamp(status['last_sync']).strftime("%Y-%m-%d %H:%M:%S")
            status_text += f"上次同步: {last_sync_time}\n"
        
        return status_text

    def sync_config_to_gist_now(self):
        """Manually trigger configuration sync to Gist."""
        if not self.auto_gist_sync.is_enabled():
            QMessageBox.information(self, "提示", "请先启用自动同步功能")
            return
        
        self.set_busy(True, "状态：正在同步配置到 Gist...")
        success, message = self.auto_gist_sync.auto_upload_config()
        self.set_busy(False, "状态：就绪")
        
        if success:
            QMessageBox.information(self, "成功", message)
            self.log(f"✅ {message}")
        else:
            QMessageBox.warning(self, "错误", message)
            self.log(f"❌ 同步失败: {message}")

    def sync_config_from_gist_now(self):
        """Manually trigger configuration sync from Gist."""
        if not self.auto_gist_sync.is_enabled():
            QMessageBox.information(self, "提示", "请先启用自动同步功能")
            return
        
        self.set_busy(True, "状态：正在从 Gist 同步配置...")
        success, message = self.auto_gist_sync.auto_download_config()
        self.set_busy(False, "状态：就绪")
        
        if success:
            QMessageBox.information(self, "成功", message)
            self.log(f"✅ {message}")
            self._refresh_owner_label()
        else:
            QMessageBox.warning(self, "错误", message)
            self.log(f"❌ 同步失败: {message}")

    def open_log_file(self):
        self._open_local_path(get_log_file_path())

    def clear_log_panel(self):
        self.log_text.clear()

    def _open_local_path(self, path: Path) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except Exception:
            QMessageBox.information(self, "提示", f"请手动打开文件：{path}")

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

    def open_advanced_settings(self):
        """Open advanced settings dialog."""
        dialog = AdvancedSettingsDialog(self)
        dialog.exec()

    def start_local_generate(self):
        """Use local language rules to classify repos."""
        if not self._ensure_repo_groups_file():
            return
            
        owner = self._resolve_owner_for_sync()
        if not owner:
            return

        if self._has_existing_classification():
            overwrite_reply = QMessageBox.question(
                self,
                "⚠️ 自动分类确认",
                "检测到 REPO-GROUPS.md 已存在分类内容。\n"
                "执行按语言自动分类将会重新归类尚未分类的仓库。\n\n"
                "是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if overwrite_reply != QMessageBox.StandardButton.Yes:
                return

        groups, tags = repo_config.load_groups_from_file(self.config_file)

        self.set_busy(True, "状态：按语言自动分类中...")
        self.log("🤖 开始按语言自动分类（生成 REPO-GROUPS.md）...")

        self.local_generate_worker = LocalGenerateWorker(
            owner,
            self.token,
            self.config_file,
            groups,
            tags
        )
        self.local_generate_worker.progress.connect(self.on_generate_progress)
        self.local_generate_worker.finished.connect(self.on_generate_finished)
        self.local_generate_worker.start()

    def on_generate_progress(self, current: int, total: int):
        self.status_label.setText(f"状态：自动分类中... ({current}/{total})")

    def on_generate_finished(self, success: bool, total: int, error: str):
        self.set_busy(False, "状态：就绪")
        if not success:
            QMessageBox.critical(self, "分类失败", error)
            self.log(f"❌ 分类失败: {error}")
            return

        self.log(f"✅ 分类完成，共 {total} 个仓库")
        QMessageBox.information(self, "完成", "分类已写入 REPO-GROUPS.md，可直接手动微调")
        self._refresh_owner_label()
        self._set_flow_hint("下一步：手动微调分类文件，然后开始克隆")
        self.open_repo_groups_file()
        
        # 触发自动同步
        self._trigger_auto_sync_on_change()

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
            return self.login_name

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
        if not self._ensure_repo_groups_file():
            return

        self.set_busy(True, "状态：增量更新中（拉取新增仓库）...")
        self.new_repos = []

        self.log("🔄 开始增量更新：拉取新增仓库...")

        owner_override = self._resolve_owner_for_sync()

        self.sync_worker = SyncWorker(
            self.config_file,
            owner_override=owner_override,
            token=self.token or "",
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
            self.log(f"✅ 发现 {len(new_repos)} 个新增仓库，准备写入“未分类”")
            preview = "\n".join(f"  - {name}" for name in new_repos[:20])
            suffix = "\n  ..." if len(new_repos) > 20 else ""
            self.log(f"📋 新增仓库列表:\n{preview}{suffix}")
            self.set_busy(True, "状态：增量更新中（写入未分类）...")
            self.apply_worker = ApplyWorker(self.config_file, self.new_repos)
            self.apply_worker.finished.connect(self.on_incremental_apply_finished)
            self.apply_worker.start()
        else:
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
        
        # 触发自动同步
        self._trigger_auto_sync_on_change()

    def _set_progress(self, phase: str, done: int, total: int, success: int, fail: int):
        if total <= 0:
            self.progress_bar.setRange(0, 0)
            self.progress_detail_label.setText(f"阶段：{phase}，进度未知")
            return

        percent = int((done / total) * 100)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(max(0, min(100, percent)))

        phase_label = {
            "clone": "克隆",
            "check": "完整性检查",
            "pull": "批量更新",
        }.get(phase, phase)
        self.progress_detail_label.setText(
            f"阶段：{phase_label} | 进度：{done}/{total} | 成功 {success} | 失败 {fail}"
        )

    def _run_clone_with_config(self, config_file: str, log_prefix: str = "🚀 开始批量克隆..."):
        if not Path(config_file).exists():
            QMessageBox.warning(self, "错误", f"配置文件不存在：{config_file}")
            return

        self.current_execution_label = "克隆"
        self.set_busy(True, "状态：克隆中...")
        self.log(log_prefix)

        self.clone_worker = CloneWorker(
            config_file,
            tasks=self.parallel_tasks,
            connections=self.parallel_connections,
            token=self.token or "",
        )
        self.clone_worker.log_signal.connect(self.log)
        self.clone_worker.progress_signal.connect(self._set_progress)
        self.clone_worker.finished.connect(self.on_clone_finished)
        self.clone_worker.start()

    def start_pull(self):
        if not self._ensure_repo_groups_file():
            return

        self.current_execution_label = "批量更新"
        self.set_busy(True, "状态：批量更新中...")
        self.log("🔄 开始批量更新已克隆仓库...")

        self.pull_worker = PullWorker(
            self.config_file,
            tasks=self.parallel_tasks,
            token=self.token or "",
        )
        self.pull_worker.log_signal.connect(self.log)
        self.pull_worker.progress_signal.connect(self._set_progress)
        self.pull_worker.finished.connect(self.on_pull_finished)
        self.pull_worker.start()

    def on_pull_finished(self, success: bool, result: Dict[str, Any], error: str):
        self.set_busy(False, "状态：就绪")

        if not success:
            QMessageBox.critical(self, "❌ 错误", f"批量更新失败:\n{error}")
            self.log(f"❌ 错误: {error}")
            return

        self._refresh_owner_label()
        summary = self._format_summary("批量更新完成", result)
        self.status_label.setText(f"状态：{summary}")
        self.log(f"✅ {summary}")

        failed_reasons = result.get("failed_reasons", {})
        if isinstance(failed_reasons, dict) and failed_reasons:
            self.log("⚠️ 批量更新失败原因详情：")
            for repo_full, reason_code in failed_reasons.items():
                reason_text = self._format_pull_failure_reason(str(reason_code))
                self.log(f"   - {repo_full}: {reason_text} ({reason_code})")

        if result.get("fail", 0) > 0:
            QMessageBox.warning(
                self,
                "⚠️ 部分失败",
                f"失败 {result.get('fail', 0)} 个仓库，失败列表已生成：\n{FAILED_REPOS_FILE}",
            )

        self._show_result_summary("批量更新", result)

    def retry_failed_repos(self):
        failed_path = FAILED_REPOS_FILE
        if not failed_path.exists():
            QMessageBox.information(self, "提示", f"未找到失败列表：\n{failed_path}")
            return

        self._run_clone_with_config(str(failed_path), "🔁 开始按 failed-repos.txt 重试失败仓库...")

    def start_clone(self):
        if not self._ensure_repo_groups_file():
            return
        self._run_clone_with_config(self.config_file)

    def on_clone_finished(self, success: bool, result: Dict[str, Any], error: str):
        self.set_busy(False, "状态：就绪")

        if not success:
            QMessageBox.critical(self, "❌ 错误", f"克隆失败:\n{error}")
            self.log(f"❌ 错误: {error}")
            return

        self._refresh_owner_label()
        summary = self._format_summary(f"{self.current_execution_label}完成", result)
        self.status_label.setText(f"状态：{summary}")
        self.log(f"✅ {summary}")

        if result.get("fail", 0) > 0:
            QMessageBox.warning(
                self,
                "⚠️ 部分失败",
                f"失败 {result.get('fail', 0)} 个仓库，失败列表已生成：\n{FAILED_REPOS_FILE}"
            )

        self._show_result_summary(self.current_execution_label, result)

    def _show_result_summary(self, action: str, result: Dict[str, Any]):
        total = result.get("total", 0)
        success = result.get("success", 0)
        fail = result.get("fail", 0)
        duration = result.get("duration", 0)
        success_rate = (success / total * 100) if total else 0.0

        lines = [
            f"操作：{action}",
            f"总仓库：{total}",
            f"成功：{success}",
            f"失败：{fail}",
            f"成功率：{success_rate:.1f}%",
            f"耗时：{self._format_duration(duration)}",
        ]

        failed_file = result.get("failed_file", "")
        if failed_file:
            lines.append(f"失败列表：{failed_file}")

        message = "\n".join(lines)
        QMessageBox.information(self, "执行结果", message)

    @staticmethod
    def _format_pull_failure_reason(reason_code: str) -> str:
        return {
            "local_repo_missing": "本地仓库缺失（目录不存在或不是 Git 仓库）",
            "not_git_repo": "目录不是 Git 仓库",
            "remote_ref_missing": "远端分支/引用不存在",
            "local_changes_conflict": "本地有未提交改动，无法 fast-forward",
            "unrelated_histories": "本地与远端历史不相关",
            "not_fast_forward": "无法快进更新（需手工处理分叉）",
            "network_error": "网络连接失败",
            "auth_error": "认证失败或权限不足",
            "canceled": "任务已取消",
            "exception": "执行异常",
            "unknown": "未知错误",
        }.get(reason_code, "未知错误")

    def _format_summary(self, prefix: str, result: Dict[str, Any]) -> str:
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
        scroll_bar = self.log_text.verticalScrollBar()
        stick_to_bottom = scroll_bar.value() >= max(0, scroll_bar.maximum() - 4)
        self.log_text.appendPlainText(message)
        if stick_to_bottom or self.log_text.blockCount() <= 2:
            scroll_bar.setValue(scroll_bar.maximum())

    def _trigger_auto_sync_on_change(self):
        """Trigger auto sync when configuration changes."""
        # 无需检查 is_enabled，内部会根据 Token 自动判断
        
        # 在后台线程中执行自动同步，避免阻塞 UI
        try:
            success, message = self.auto_gist_sync.sync_on_config_change()
            if success:
                self.log(f"🔄 [自动同步] {message}")
            # 只有在真正发生错误或成功的操作时才记录，减少日志噪音
        except Exception as e:
            self.log(f"⚠️ 自动同步异常: {e}")

    def update_auto_sync_token(self, new_token: str):
        """Update auto sync instance with new token."""
        self.auto_gist_sync = get_auto_gist_sync(self.config_file)
        if self.auto_gist_sync.is_enabled():
            self.log("🔄 已更新自动同步认证信息")



def main():
    app = QApplication(sys.argv)
    window = MainWindow(app)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
