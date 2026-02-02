#!/usr/bin/env python3
# GitHub 仓库同步 GUI：使用 PyQt5 实现可视化同步预览与应用
#
# 主要功能：
#   - 选择/检测 REPO-GROUPS.md 文件
#   - 预览新增仓库列表
#   - 确认后写入"未分类"分组
#
# 使用方式：
#   python gui.py

import sys
from pathlib import Path
from typing import List

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QFileDialog, QMessageBox,
    QProgressBar, QTextEdit, QFrame, QComboBox, QMenuBar, QMenu, QAction
)
from qt_material import apply_stylesheet, list_themes

from lib.config import CONFIG_FILE
from lib.sync import preview_sync, apply_sync
from lib.paths import SCRIPT_DIR


# 推荐的主题列表（精选）
RECOMMENDED_THEMES = {
    "深色主题": [
        "dark_teal.xml",
        "dark_blue.xml",
        "dark_cyan.xml",
        "dark_purple.xml",
        "dark_amber.xml",
    ],
    "浅色主题": [
        "light_teal.xml",
        "light_blue.xml",
        "light_cyan.xml",
        "light_purple.xml",
        "light_amber.xml",
    ]
}


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


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.config_file = str(SCRIPT_DIR / CONFIG_FILE)
        self.owner = ""
        self.new_repos = []
        self.sync_worker = None
        self.apply_worker = None
        self.current_theme = "dark_teal.xml"  # 默认主题

        self.init_ui()
        self.apply_theme(self.current_theme)

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("GitHub 仓库同步工具")
        self.setMinimumSize(900, 700)

        # 创建菜单栏
        menubar = self.menuBar()
        theme_menu = menubar.addMenu("🎨 主题")

        # 深色主题子菜单
        dark_menu = QMenu("深色主题", self)
        for theme in RECOMMENDED_THEMES["深色主题"]:
            action = QAction(theme.replace(".xml", "").replace("dark_", "").title(), self)
            action.triggered.connect(lambda checked, t=theme: self.apply_theme(t))
            dark_menu.addAction(action)
        theme_menu.addMenu(dark_menu)

        # 浅色主题子菜单
        light_menu = QMenu("浅色主题", self)
        for theme in RECOMMENDED_THEMES["浅色主题"]:
            action = QAction(theme.replace(".xml", "").replace("light_", "").title(), self)
            action.triggered.connect(lambda checked, t=theme: self.apply_theme(t))
            light_menu.addAction(action)
        theme_menu.addMenu(light_menu)

        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(25, 25, 25, 25)
        central_widget.setLayout(main_layout)

        # 标题区域
        title_frame = QFrame()
        title_layout = QVBoxLayout()
        title_frame.setLayout(title_layout)

        title_label = QLabel("🚀 GitHub 仓库同步工具")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 18pt; font-weight: bold;")
        title_layout.addWidget(title_label)

        subtitle_label = QLabel("同步公共仓库到 REPO-GROUPS.md 的\"未分类\"分组")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("font-size: 9pt;")
        title_layout.addWidget(subtitle_label)

        main_layout.addWidget(title_frame)

        # 内容区域
        content_frame = QFrame()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(15)
        content_frame.setLayout(content_layout)

        # 文件选择区域
        file_group_label = QLabel("📁 配置文件")
        file_group_label.setStyleSheet("font-size: 11pt; font-weight: bold;")
        content_layout.addWidget(file_group_label)

        file_layout = QHBoxLayout()
        self.file_label = QLabel(f"{self.config_file}")
        self.file_label.setWordWrap(True)
        self.file_label.setStyleSheet("padding: 10px; border-radius: 6px;")
        file_layout.addWidget(self.file_label, 1)

        self.select_file_btn = QPushButton("选择文件")
        self.select_file_btn.clicked.connect(self.select_file)
        self.select_file_btn.setFixedWidth(100)
        file_layout.addWidget(self.select_file_btn)

        content_layout.addLayout(file_layout)

        # Owner 显示
        self.owner_label = QLabel("👤 仓库所有者: 未检测")
        self.owner_label.setStyleSheet("font-size: 11pt;")
        content_layout.addWidget(self.owner_label)

        # 同步预览按钮
        self.preview_btn = QPushButton("🔍 同步预览")
        self.preview_btn.clicked.connect(self.preview_sync)
        self.preview_btn.setCursor(Qt.PointingHandCursor)
        content_layout.addWidget(self.preview_btn)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        content_layout.addWidget(self.progress_bar)

        # 新增仓库列表
        list_label = QLabel("📦 新增仓库列表")
        list_label.setStyleSheet("font-size: 11pt; font-weight: bold; margin-top: 10px;")
        content_layout.addWidget(list_label)

        self.repo_list = QListWidget()
        self.repo_list.setMinimumHeight(200)
        content_layout.addWidget(self.repo_list)

        # 统计信息
        self.stats_label = QLabel("📊 新增仓库数: 0")
        self.stats_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        content_layout.addWidget(self.stats_label)

        # 应用按钮
        self.apply_btn = QPushButton("✅ 写入未分类")
        self.apply_btn.clicked.connect(self.apply_sync)
        self.apply_btn.setEnabled(False)
        self.apply_btn.setCursor(Qt.PointingHandCursor)
        content_layout.addWidget(self.apply_btn)

        # 日志区域
        log_label = QLabel("📝 操作日志")
        log_label.setStyleSheet("font-size: 11pt; font-weight: bold; margin-top: 10px;")
        content_layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        content_layout.addWidget(self.log_text)

        main_layout.addWidget(content_frame)

    def apply_theme(self, theme_name: str):
        """应用主题"""
        try:
            apply_stylesheet(self.app, theme=theme_name)
            self.current_theme = theme_name
            self.log(f"🎨 已切换到主题: {theme_name.replace('.xml', '')}")
        except Exception as e:
            self.log(f"❌ 主题切换失败: {e}")

    def select_file(self):
        """选择配置文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 REPO-GROUPS.md 文件",
            str(SCRIPT_DIR),
            "Markdown Files (*.md);;All Files (*)"
        )

        if file_path:
            self.config_file = file_path
            self.file_label.setText(f"{self.config_file}")
            self.log(f"✅ 已选择文件: {self.config_file}")

    def preview_sync(self):
        """预览同步"""
        if not Path(self.config_file).exists():
            QMessageBox.warning(self, "错误", f"配置文件不存在: {self.config_file}")
            return

        # 禁用按钮
        self.preview_btn.setEnabled(False)
        self.apply_btn.setEnabled(False)
        self.select_file_btn.setEnabled(False)

        # 显示进度条
        self.progress_bar.setVisible(True)

        # 清空列表
        self.repo_list.clear()
        self.new_repos = []

        # 记录日志
        self.log("🔄 开始同步预览...")

        # 启动工作线程
        self.sync_worker = SyncWorker(self.config_file)
        self.sync_worker.finished.connect(self.on_preview_finished)
        self.sync_worker.start()

    def on_preview_finished(self, success: bool, owner: str, new_repos: List[str], error: str):
        """预览完成回调"""
        # 隐藏进度条
        self.progress_bar.setVisible(False)

        # 启用按钮
        self.preview_btn.setEnabled(True)
        self.select_file_btn.setEnabled(True)

        if not success:
            QMessageBox.critical(self, "❌ 错误", f"同步预览失败:\n{error}")
            self.log(f"❌ 错误: {error}")
            return

        self.owner = owner
        self.new_repos = new_repos

        # 更新 owner 显示
        self.owner_label.setText(f"👤 仓库所有者: {owner}")

        # 更新列表
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
        """应用同步"""
        if not self.new_repos:
            QMessageBox.warning(self, "⚠️ 警告", "没有新增仓库需要写入")
            return

        # 确认对话框
        reply = QMessageBox.question(
            self,
            "❓ 确认",
            f"确定要将 {len(self.new_repos)} 个新增仓库写入\"未分类\"分组吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # 禁用按钮
        self.preview_btn.setEnabled(False)
        self.apply_btn.setEnabled(False)
        self.select_file_btn.setEnabled(False)

        # 显示进度条
        self.progress_bar.setVisible(True)

        # 记录日志
        self.log("💾 开始写入未分类...")

        # 启动工作线程
        self.apply_worker = ApplyWorker(self.config_file, self.new_repos)
        self.apply_worker.finished.connect(self.on_apply_finished)
        self.apply_worker.start()

    def on_apply_finished(self, success: bool, error: str):
        """应用完成回调"""
        # 隐藏进度条
        self.progress_bar.setVisible(False)

        # 启用按钮
        self.preview_btn.setEnabled(True)
        self.select_file_btn.setEnabled(True)

        if not success:
            QMessageBox.critical(self, "❌ 错误", f"写入失败:\n{error}")
            self.log(f"❌ 错误: {error}")
            self.apply_btn.setEnabled(True)
            return

        # 成功提示
        QMessageBox.information(
            self,
            "✅ 成功",
            f"成功写入 {len(self.new_repos)} 个仓库到\"未分类\"分组"
        )
        self.log(f"✅ 成功写入 {len(self.new_repos)} 个仓库")

        # 清空列表
        self.repo_list.clear()
        self.new_repos = []
        self.stats_label.setText("📊 新增仓库数: 0")
        self.apply_btn.setEnabled(False)

    def log(self, message: str):
        """记录日志"""
        self.log_text.append(message)


def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = MainWindow(app)
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
