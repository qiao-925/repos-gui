#!/usr/bin/env python3
# GitHub 仓库管理 GUI：单页操作，覆盖同步/克隆/检查
#
# 使用方式：
#   python gui.py

import sys
import time
from pathlib import Path
from typing import List, Dict

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QFileDialog, QMessageBox,
    QProgressBar, QTextEdit, QFrame, QSpinBox, QFormLayout
)

try:
    from qt_material import apply_stylesheet
    HAS_QT_MATERIAL = True
except Exception:
    HAS_QT_MATERIAL = False

from lib import config
from lib.config import CONFIG_FILE, parse_repo_groups
from lib.sync import preview_sync, apply_sync
from lib.paths import SCRIPT_DIR
from lib.parallel import execute_parallel_clone
from lib.check import check_repos_parallel
from lib.failed_repos import save_failed_repos
from lib.logger import set_log_callback, get_log_state


DEFAULT_TASKS = 5
DEFAULT_CONNECTIONS = 8
CHECK_TIMEOUT = 30
FAILED_REPOS_FILE = SCRIPT_DIR / "failed-repos.txt"


class SyncWorker(QThread):
    """同步预览工作线程"""
    finished = pyqtSignal(bool, str, list, str)  # 成功标志, owner, 新增仓库列表, 错误信息

    def __init__(self, config_file: str):
        super().__init__()
        self.config_file = config_file

    def run(self):
        success, owner, new_repos, error = preview_sync(self.config_file)
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


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.config_file = str(SCRIPT_DIR / CONFIG_FILE)
        self.new_repos: List[str] = []
        self.sync_worker = None
        self.apply_worker = None
        self.clone_worker = None
        self.check_worker = None

        self.init_ui()
        if HAS_QT_MATERIAL:
            try:
                apply_stylesheet(self.app, theme="light_teal.xml")
            except Exception:
                pass

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("GitHub 仓库管理工具")
        self.setMinimumSize(920, 760)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(24, 24, 24, 24)
        central_widget.setLayout(main_layout)

        # 标题区域
        title_frame = QFrame()
        title_layout = QVBoxLayout()
        title_frame.setLayout(title_layout)

        title_label = QLabel("🚀 GitHub 仓库管理工具")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 18pt; font-weight: bold;")
        title_layout.addWidget(title_label)

        subtitle_label = QLabel("同步 / 批量克隆 / 完整性检查 - 单页操作")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("font-size: 9pt;")
        title_layout.addWidget(subtitle_label)

        main_layout.addWidget(title_frame)

        # 文件选择区域
        file_label = QLabel("📁 任务列表文件（REPO-GROUPS.md 格式）")
        file_label.setStyleSheet("font-size: 11pt; font-weight: bold;")
        main_layout.addWidget(file_label)

        file_layout = QHBoxLayout()
        self.file_label = QLabel(self.config_file)
        self.file_label.setWordWrap(True)
        self.file_label.setStyleSheet("padding: 8px; border-radius: 6px;")
        file_layout.addWidget(self.file_label, 1)

        self.select_file_btn = QPushButton("选择文件")
        self.select_file_btn.clicked.connect(self.select_file)
        self.select_file_btn.setFixedWidth(100)
        file_layout.addWidget(self.select_file_btn)

        self.reset_file_btn = QPushButton("使用默认")
        self.reset_file_btn.clicked.connect(self.reset_file)
        self.reset_file_btn.setFixedWidth(100)
        file_layout.addWidget(self.reset_file_btn)

        main_layout.addLayout(file_layout)

        failed_label = QLabel(f"失败列表：{FAILED_REPOS_FILE}（自动生成，可直接选择重试）")
        failed_label.setStyleSheet("font-size: 9pt; color: #666;")
        main_layout.addWidget(failed_label)

        self.owner_label = QLabel("👤 仓库所有者: 未检测")
        self.owner_label.setStyleSheet("font-size: 11pt;")
        main_layout.addWidget(self.owner_label)

        # 参数设置
        params_label = QLabel("⚙️ 并行参数（可选）")
        params_label.setStyleSheet("font-size: 11pt; font-weight: bold; margin-top: 6px;")
        main_layout.addWidget(params_label)

        params_frame = QFrame()
        params_layout = QFormLayout()
        params_layout.setLabelAlignment(Qt.AlignRight)
        params_layout.setFormAlignment(Qt.AlignLeft)
        params_layout.setHorizontalSpacing(16)
        params_frame.setLayout(params_layout)

        self.tasks_spin = QSpinBox()
        self.tasks_spin.setRange(1, 64)
        self.tasks_spin.setValue(DEFAULT_TASKS)

        self.connections_spin = QSpinBox()
        self.connections_spin.setRange(1, 64)
        self.connections_spin.setValue(DEFAULT_CONNECTIONS)

        params_layout.addRow("并行任务数", self.tasks_spin)
        params_layout.addRow("并行连接数", self.connections_spin)
        main_layout.addWidget(params_frame)

        reset_params_layout = QHBoxLayout()
        reset_params_layout.addStretch(1)
        self.reset_params_btn = QPushButton("恢复默认参数")
        self.reset_params_btn.clicked.connect(self.reset_params)
        self.reset_params_btn.setFixedWidth(160)
        reset_params_layout.addWidget(self.reset_params_btn)
        main_layout.addLayout(reset_params_layout)

        # 操作按钮
        actions_label = QLabel("▶ 操作")
        actions_label.setStyleSheet("font-size: 11pt; font-weight: bold; margin-top: 8px;")
        main_layout.addWidget(actions_label)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)

        self.preview_btn = QPushButton("🔍 同步预览")
        self.preview_btn.clicked.connect(self.preview_sync)
        self.preview_btn.setCursor(Qt.PointingHandCursor)
        actions_layout.addWidget(self.preview_btn)

        self.apply_btn = QPushButton("✅ 写入未分类")
        self.apply_btn.clicked.connect(self.apply_sync)
        self.apply_btn.setEnabled(False)
        self.apply_btn.setCursor(Qt.PointingHandCursor)
        actions_layout.addWidget(self.apply_btn)

        self.clone_btn = QPushButton("📥 开始克隆")
        self.clone_btn.clicked.connect(self.start_clone)
        self.clone_btn.setCursor(Qt.PointingHandCursor)
        actions_layout.addWidget(self.clone_btn)

        self.check_btn = QPushButton("🧪 仅检查")
        self.check_btn.clicked.connect(self.start_check)
        self.check_btn.setCursor(Qt.PointingHandCursor)
        actions_layout.addWidget(self.check_btn)

        main_layout.addLayout(actions_layout)

        # 进度条 + 状态
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("状态：就绪")
        self.status_label.setStyleSheet("font-size: 10pt; color: #444;")
        main_layout.addWidget(self.status_label)

        # 新增仓库列表
        list_label = QLabel("📦 新增仓库列表（同步预览后显示）")
        list_label.setStyleSheet("font-size: 11pt; font-weight: bold; margin-top: 8px;")
        main_layout.addWidget(list_label)

        self.repo_list = QListWidget()
        self.repo_list.setMinimumHeight(160)
        main_layout.addWidget(self.repo_list)

        self.stats_label = QLabel("📊 新增仓库数: 0")
        self.stats_label.setStyleSheet("font-size: 11pt; font-weight: bold;")
        main_layout.addWidget(self.stats_label)

        # 日志区域
        log_label = QLabel("📝 操作日志")
        log_label.setStyleSheet("font-size: 11pt; font-weight: bold; margin-top: 6px;")
        main_layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(160)
        main_layout.addWidget(self.log_text)

    def set_busy(self, busy: bool, status: str = ""):
        self.select_file_btn.setEnabled(not busy)
        self.reset_file_btn.setEnabled(not busy)
        self.reset_params_btn.setEnabled(not busy)
        self.preview_btn.setEnabled(not busy)
        self.clone_btn.setEnabled(not busy)
        self.check_btn.setEnabled(not busy)
        self.apply_btn.setEnabled(not busy and bool(self.new_repos))
        self.progress_bar.setVisible(busy)
        if status:
            self.status_label.setText(status)

    def reset_file(self):
        self.config_file = str(SCRIPT_DIR / CONFIG_FILE)
        self.file_label.setText(self.config_file)
        self.log(f"✅ 已恢复默认文件: {self.config_file}")

    def reset_params(self):
        self.tasks_spin.setValue(DEFAULT_TASKS)
        self.connections_spin.setValue(DEFAULT_CONNECTIONS)
        self.log("✅ 已恢复默认参数")

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 REPO-GROUPS.md 文件",
            str(SCRIPT_DIR),
            "Markdown Files (*.md);;All Files (*)"
        )

        if file_path:
            self.config_file = file_path
            self.file_label.setText(self.config_file)
            self.log(f"✅ 已选择文件: {self.config_file}")

    def preview_sync(self):
        if not Path(self.config_file).exists():
            QMessageBox.warning(self, "错误", f"配置文件不存在: {self.config_file}")
            return

        self.set_busy(True, "状态：同步预览中...")
        self.repo_list.clear()
        self.new_repos = []

        self.log("🔄 开始同步预览...")

        self.sync_worker = SyncWorker(self.config_file)
        self.sync_worker.finished.connect(self.on_preview_finished)
        self.sync_worker.start()

    def on_preview_finished(self, success: bool, owner: str, new_repos: List[str], error: str):
        self.set_busy(False, "状态：就绪")

        if not success:
            QMessageBox.critical(self, "❌ 错误", f"同步预览失败:\n{error}")
            self.log(f"❌ 错误: {error}")
            return

        self.owner_label.setText(f"👤 仓库所有者: {owner}")
        self.new_repos = new_repos

        if new_repos:
            self.repo_list.addItems(new_repos)
            self.stats_label.setText(f"📊 新增仓库数: {len(new_repos)}")
            self.apply_btn.setEnabled(True)
            self.log(f"✅ 发现 {len(new_repos)} 个新增仓库")
        else:
            self.stats_label.setText("📊 新增仓库数: 0")
            self.log("ℹ️ 没有新增仓库，REPO-GROUPS.md 已是最新")
            QMessageBox.information(self, "ℹ️ 提示", "没有新增仓库，REPO-GROUPS.md 已是最新")

    def apply_sync(self):
        if not self.new_repos:
            QMessageBox.warning(self, "⚠️ 警告", "没有新增仓库需要写入")
            return

        reply = QMessageBox.question(
            self,
            "❓ 确认",
            f"确定要将 {len(self.new_repos)} 个新增仓库写入\"未分类\"分组吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        self.set_busy(True, "状态：写入未分类中...")
        self.log("💾 开始写入未分类...")

        self.apply_worker = ApplyWorker(self.config_file, self.new_repos)
        self.apply_worker.finished.connect(self.on_apply_finished)
        self.apply_worker.start()

    def on_apply_finished(self, success: bool, error: str):
        self.set_busy(False, "状态：就绪")

        if not success:
            QMessageBox.critical(self, "❌ 错误", f"写入失败:\n{error}")
            self.log(f"❌ 错误: {error}")
            self.apply_btn.setEnabled(True)
            return

        QMessageBox.information(
            self,
            "✅ 成功",
            f"成功写入 {len(self.new_repos)} 个仓库到\"未分类\"分组"
        )
        self.log(f"✅ 成功写入 {len(self.new_repos)} 个仓库")

        self.repo_list.clear()
        self.new_repos = []
        self.stats_label.setText("📊 新增仓库数: 0")
        self.apply_btn.setEnabled(False)

    def start_clone(self):
        if not Path(self.config_file).exists():
            QMessageBox.warning(self, "错误", f"配置文件不存在: {self.config_file}")
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
        if not Path(self.config_file).exists():
            QMessageBox.warning(self, "错误", f"配置文件不存在: {self.config_file}")
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
        if config.REPO_OWNER:
            self.owner_label.setText(f"👤 仓库所有者: {config.REPO_OWNER}")

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
