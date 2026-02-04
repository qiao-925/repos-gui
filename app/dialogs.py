# Classification dialog

import functools
from typing import Dict, List

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QVBoxLayout, QInputDialog
)

from lib import ai, repo_groups
from app.workers import RepoFetchWorker, AiClassifyWorker

class ClassifyDialog(QDialog):
    """仓库分类面板"""

    def __init__(self, owner: str, token: str, config_file: str, parent=None):
        super().__init__(parent)
        self.owner = owner
        self.token = token
        self.config_file = config_file
        self.repos: List[Dict[str, object]] = []
        self.repo_groups: Dict[str, str] = {}
        self.groups, self.group_tags = repo_groups.load_groups_from_file(config_file)
        if not self.groups:
            self.groups = ["Go-Practice", "Java-Practice", "AI-Practice", "Tools", "Daily", "未分类"]
        if "未分类" not in self.groups:
            self.groups.append("未分类")

        self.ai_key, _ = ai.load_api_key()
        self.ai_base_url, self.ai_model = ai.load_ai_config()

        self.fetch_worker = None
        self.ai_worker = None

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("仓库分类")
        self.setMinimumSize(900, 720)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        self.setLayout(layout)

        info_layout = QHBoxLayout()
        self.owner_label = QLabel(f"账号：{self.owner or '未登录'}")
        info_layout.addWidget(self.owner_label, 1)

        self.repo_count_label = QLabel("仓库数：0")
        info_layout.addWidget(self.repo_count_label)
        layout.addLayout(info_layout)

        btn_layout = QHBoxLayout()
        self.fetch_btn = QPushButton("拉取仓库")
        self.fetch_btn.clicked.connect(self.fetch_repos)
        btn_layout.addWidget(self.fetch_btn)

        self.ai_btn = QPushButton("AI 分类")
        self.ai_btn.clicked.connect(self.ai_classify)
        btn_layout.addWidget(self.ai_btn)

        self.ai_settings_btn = QPushButton("AI 设置")
        self.ai_settings_btn.clicked.connect(self.configure_ai)
        btn_layout.addWidget(self.ai_settings_btn)

        self.save_btn = QPushButton("写入分类文件")
        self.save_btn.clicked.connect(self.save_repo_groups)
        btn_layout.addWidget(self.save_btn)

        btn_layout.addStretch(1)
        layout.addLayout(btn_layout)

        filter_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索仓库名 / 描述 / 语言")
        self.search_input.textChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.search_input, 1)

        self.batch_combo = QComboBox()
        self.batch_combo.addItems(self.groups)
        filter_layout.addWidget(self.batch_combo)

        self.apply_group_btn = QPushButton("批量设置")
        self.apply_group_btn.clicked.connect(self.apply_group_to_selection)
        filter_layout.addWidget(self.apply_group_btn)

        self.add_group_btn = QPushButton("新建分组")
        self.add_group_btn.clicked.connect(self.add_group)
        filter_layout.addWidget(self.add_group_btn)

        layout.addLayout(filter_layout)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["仓库", "描述", "语言", "分组"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table, 1)

        self.status_label = QLabel("状态：就绪")
        layout.addWidget(self.status_label)

        self.update_buttons()

    def update_buttons(self):
        has_token = bool(self.token)
        self.fetch_btn.setEnabled(has_token and bool(self.owner))
        self.ai_btn.setEnabled(bool(self.repos))
        self.save_btn.setEnabled(bool(self.repo_groups))

    def fetch_repos(self):
        if not self.owner:
            QMessageBox.warning(self, "提示", "未检测到登录账号")
            return
        self.set_status("状态：拉取仓库中...")
        self.fetch_btn.setEnabled(False)

        self.fetch_worker = RepoFetchWorker(self.owner, self.token)
        self.fetch_worker.finished.connect(self.on_fetch_finished)
        self.fetch_worker.start()

    def on_fetch_finished(self, success: bool, repos: List[Dict[str, object]], error: str):
        if not success:
            QMessageBox.critical(self, "拉取失败", error)
            self.set_status("状态：就绪")
            self.fetch_btn.setEnabled(True)
            return

        self.repos = sorted(repos, key=lambda r: r.get("name", ""))
        self.repo_groups = {repo.get("name", ""): "未分类" for repo in self.repos}
        self.repo_count_label.setText(f"仓库数：{len(self.repos)}")
        self.refresh_table()
        self.set_status("状态：拉取完成")
        self.fetch_btn.setEnabled(True)
        self.update_buttons()

    def refresh_table(self):
        self.table.setRowCount(len(self.repos))
        for row, repo in enumerate(self.repos):
            name = str(repo.get("name", ""))
            desc = str(repo.get("description", "") or "")
            lang = str(repo.get("language", "") or "")
            topics = repo.get("topics") or []
            tooltip = ", ".join(topics) if topics else ""

            name_item = QTableWidgetItem(name)
            if tooltip:
                name_item.setToolTip(tooltip)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(desc))
            self.table.setItem(row, 2, QTableWidgetItem(lang))

            combo = QComboBox()
            combo.addItems(self.groups)
            combo.setCurrentText(self.repo_groups.get(name, "未分类"))
            combo.currentTextChanged.connect(functools.partial(self.on_group_changed, name))
            self.table.setCellWidget(row, 3, combo)

        self.apply_filter(self.search_input.text())

    def on_group_changed(self, repo_name: str, group_name: str):
        self.repo_groups[repo_name] = group_name

    def apply_filter(self, text: str):
        keyword = text.strip().lower()
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            desc_item = self.table.item(row, 1)
            lang_item = self.table.item(row, 2)
            hay = " ".join(filter(None, [
                name_item.text() if name_item else "",
                desc_item.text() if desc_item else "",
                lang_item.text() if lang_item else "",
            ])).lower()
            hidden = bool(keyword) and keyword not in hay
            self.table.setRowHidden(row, hidden)

    def apply_group_to_selection(self):
        group = self.batch_combo.currentText().strip()
        if not group:
            return
        for idx in self.table.selectionModel().selectedRows():
            row = idx.row()
            name_item = self.table.item(row, 0)
            if not name_item:
                continue
            name = name_item.text()
            self.repo_groups[name] = group
            combo = self.table.cellWidget(row, 3)
            if isinstance(combo, QComboBox):
                combo.setCurrentText(group)

    def add_group(self):
        group, ok = QInputDialog.getText(self, "新建分组", "请输入分组名称：")
        if not ok or not group.strip():
            return
        group = group.strip()
        if group in self.groups:
            QMessageBox.information(self, "提示", "分组已存在")
            return
        self.groups.append(group)
        self.batch_combo.addItem(group)
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 3)
            if isinstance(combo, QComboBox):
                combo.addItem(group)

    def configure_ai(self):
        api_key, _ = ai.load_api_key()
        new_key, ok = QInputDialog.getText(
            self,
            "AI 设置",
            "请输入 DeepSeek API Key（留空保持不变）：",
            QLineEdit.Password
        )
        if ok and new_key.strip():
            ai.save_api_key(new_key.strip())
            self.ai_key = new_key.strip()
        else:
            self.ai_key = api_key

        base_url, ok = QInputDialog.getText(
            self,
            "AI 设置",
            "Base URL（默认 https://api.deepseek.com）：",
            text=self.ai_base_url
        )
        if ok and base_url.strip():
            self.ai_base_url = base_url.strip()

        model, ok = QInputDialog.getText(
            self,
            "AI 设置",
            "Model（默认 deepseek-chat）：",
            text=self.ai_model
        )
        if ok and model.strip():
            self.ai_model = model.strip()

        ai.save_ai_config(self.ai_base_url, self.ai_model)
        self.set_status("状态：AI 配置已更新")

    def ai_classify(self):
        if not self.repos:
            QMessageBox.information(self, "提示", "请先拉取仓库列表")
            return

        if not self.ai_key:
            api_key, ok = QInputDialog.getText(
                self,
                "AI 分类",
                "请输入 DeepSeek API Key：",
                QLineEdit.Password
            )
            if not ok or not api_key.strip():
                return
            self.ai_key = api_key.strip()
            ai.save_api_key(self.ai_key)

        self.set_status("状态：AI 分类中...")
        self.ai_btn.setEnabled(False)

        self.ai_worker = AiClassifyWorker(
            self.repos,
            self.groups,
            self.ai_key,
            self.ai_base_url,
            self.ai_model
        )
        self.ai_worker.progress.connect(self.on_ai_progress)
        self.ai_worker.finished.connect(self.on_ai_finished)
        self.ai_worker.start()

    def on_ai_progress(self, current: int, total: int):
        self.set_status(f"状态：AI 分类中... ({current}/{total})")

    def on_ai_finished(self, success: bool, mapping: Dict[str, str], error: str):
        self.ai_btn.setEnabled(True)
        if not success:
            QMessageBox.critical(self, "AI 分类失败", error)
            self.set_status("状态：就绪")
            return

        for name, group in mapping.items():
            if group and group not in self.groups:
                self.groups.append(group)
                self.batch_combo.addItem(group)
            self.repo_groups[name] = group or "未分类"

        self.refresh_table()
        self.set_status("状态：AI 分类完成")

    def save_repo_groups(self):
        if not self.repo_groups:
            QMessageBox.warning(self, "提示", "没有可写入的分类结果")
            return
        owner = self.owner
        if not owner:
            owner, ok = QInputDialog.getText(self, "仓库所有者", "请输入仓库所有者：")
            if not ok or not owner.strip():
                return
            owner = owner.strip()

        ok, error = repo_groups.write_repo_groups(
            self.config_file,
            owner,
            self.groups,
            self.repo_groups,
            self.group_tags
        )
        if not ok:
            QMessageBox.critical(self, "写入失败", error)
            return
        QMessageBox.information(self, "成功", "分类结果已写入 REPO-GROUPS.md")
        self.set_status("状态：写入完成")

    def set_status(self, text: str):
        self.status_label.setText(text)
