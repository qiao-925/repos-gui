"""Auto Gist synchronization configuration dialog."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QVBoxLayout, QCheckBox, QMessageBox, QSpinBox
)


class AutoSyncDialog(QDialog):
    """Dialog for configuring automatic Gist synchronization."""
    
    sync_requested = pyqtSignal(str, str)  # gist_id, action
    
    def __init__(self, parent=None, auto_sync_instance=None):
        super().__init__(parent)
        self.auto_sync = auto_sync_instance
        self.setWindowTitle("自动 Gist 同步设置")
        self.setModal(True)
        self.resize(600, 500)
        self.init_ui()
        self.load_status()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 状态显示
        status_group = QGroupBox("当前状态")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("正在加载状态...")
        status_layout.addWidget(self.status_label)
        
        # 操作按钮
        actions_layout = QHBoxLayout()
        self.enable_btn = QPushButton("启用自动同步")
        self.disable_btn = QPushButton("禁用自动同步")
        self.sync_upload_btn = QPushButton("立即上传")
        self.sync_download_btn = QPushButton("立即下载")
        self.auto_find_btn = QPushButton("自动发现 Gist")
        self.advanced_btn = QPushButton("高级管理...")
        
        self.enable_btn.clicked.connect(self.enable_auto_sync)
        self.disable_btn.clicked.connect(self.disable_auto_sync)
        self.sync_upload_btn.clicked.connect(self.sync_upload)
        self.sync_download_btn.clicked.connect(self.sync_download)
        self.auto_find_btn.clicked.connect(self.auto_discover_gist)
        self.advanced_btn.clicked.connect(self.open_advanced_manager)
        
        actions_layout.addWidget(self.enable_btn)
        actions_layout.addWidget(self.disable_btn)
        actions_layout.addWidget(self.sync_upload_btn)
        actions_layout.addWidget(self.sync_download_btn)
        actions_layout.addWidget(self.auto_find_btn)
        actions_layout.addWidget(self.advanced_btn)
        status_layout.addLayout(actions_layout)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # 配置设置
        config_group = QGroupBox("同步配置")
        config_layout = QFormLayout()
        
        self.gist_id_edit = QLineEdit()
        self.gist_id_edit.setPlaceholderText("输入 Gist ID 或 URL")
        config_layout.addRow("Gist ID:", self.gist_id_edit)
        
        self.auto_upload_cb = QCheckBox("自动上传配置")
        self.auto_upload_cb.setChecked(True)
        config_layout.addRow("", self.auto_upload_cb)
        
        self.auto_download_cb = QCheckBox("自动下载配置")
        self.auto_download_cb.setChecked(True)
        config_layout.addRow("", self.auto_download_cb)
        
        self.sync_interval_spin = QSpinBox()
        self.sync_interval_spin.setRange(300, 86400)  # 5分钟到24小时
        self.sync_interval_spin.setValue(3600)  # 1小时
        self.sync_interval_spin.setSuffix(" 秒")
        config_layout.addRow("同步间隔:", self.sync_interval_spin)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # 说明
        help_group = QGroupBox("使用说明")
        help_layout = QVBoxLayout()
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setMaximumHeight(150)
        help_text.setPlainText(
            "自动同步功能说明：\n\n"
            "1. 启用自动同步后，配置文件变化时会自动上传到 Gist\n"
            "2. 定期检查远程 Gist 是否有更新，有更新时自动下载\n"
            "3. 支持 AI 分类、增量更新等操作后的自动同步\n"
            "4. 冲突时优先保留本地配置\n\n"
            "注意：需要先登录 GitHub 并提供有效的 Gist ID"
        )
        help_layout.addWidget(help_text)
        help_group.setLayout(help_layout)
        layout.addWidget(help_group)
        
        # 对话框按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def load_status(self):
        """Load current auto-sync status."""
        if not self.auto_sync:
            self.status_label.setText("❌ 自动同步实例未初始化")
            return
        
        status = self.auto_sync.get_status()
        
        status_text = "自动同步状态:\n\n"
        status_text += f"启用状态: {'✅ 已启用' if status['enabled'] else '❌ 未启用'}\n"
        status_text += f"Gist ID: {status['gist_id'] or '未配置'}\n"
        status_text += f"自动上传: {'✅' if status['auto_upload'] else '❌'}\n"
        status_text += f"自动下载: {'✅' if status['auto_download'] else '❌'}\n"
        status_text += f"同步间隔: {status['sync_interval']} 秒\n"
        
        if status['last_sync'] > 0:
            from datetime import datetime
            last_sync_time = datetime.fromtimestamp(status['last_sync']).strftime("%Y-%m-%d %H:%M:%S")
            status_text += f"上次同步: {last_sync_time}\n"
        
        self.status_label.setText(status_text)
        
        # 更新配置表单
        self.gist_id_edit.setText(status['gist_id'])
        self.auto_upload_cb.setChecked(status['auto_upload'])
        self.auto_download_cb.setChecked(status['auto_download'])
        self.sync_interval_spin.setValue(status['sync_interval'])
        
        # 更新按钮状态
        self.enable_btn.setEnabled(not status['enabled'])
        self.disable_btn.setEnabled(status['enabled'])
        self.sync_upload_btn.setEnabled(status['enabled'])
        self.sync_download_btn.setEnabled(status['enabled'])
    
    def enable_auto_sync(self):
        """Enable auto-sync with current settings."""
        gist_id = self.gist_id_edit.text().strip()
        if not gist_id:
            QMessageBox.warning(self, "警告", "请输入 Gist ID")
            return
        
        # 验证 Gist ID
        from ..infra.gist_config import gist_manager
        success, validated_id, error = gist_manager.validate_gist_url(gist_id)
        if not success:
            QMessageBox.warning(self, "错误", f"无效的 Gist ID: {error}")
            return
        
        # 启用自动同步
        if self.auto_sync:
            success, message = self.auto_sync.enable_auto_sync(
                validated_id,
                auto_upload=self.auto_upload_cb.isChecked(),
                auto_download=self.auto_download_cb.isChecked()
            )
            
            if success:
                QMessageBox.information(self, "成功", message)
                self.load_status()
            else:
                QMessageBox.warning(self, "错误", message)
    
    def disable_auto_sync(self):
        """Disable auto-sync."""
        reply = QMessageBox.question(
            self, "确认", "确定要禁用自动同步吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.auto_sync:
                self.auto_sync.disable_auto_sync()
                self.load_status()
    
    def sync_upload(self):
        """Manual upload to Gist."""
        if self.auto_sync:
            self.sync_requested.emit("upload", "手动上传配置到 Gist")
    
    def sync_download(self):
        """Manual download from Gist."""
        if self.auto_sync:
            self.sync_requested.emit("download", "手动从 Gist 下载配置")

    def auto_discover_gist(self):
        """Automatically find configuration gist from user's account."""
        from ..infra.gist_config import gist_manager
        from ..infra.auth import load_token
        
        token, _ = load_token()
        if not token:
            QMessageBox.warning(self, "警告", "请先登录 GitHub 账号")
            return
            
        self.status_label.setText("正在搜索您的 Gists...")
        self.auto_find_btn.setEnabled(False)
        
        # 为了保持响应，这里简单处理，实际生产中应使用 QThread
        success, gists, error = gist_manager.list_user_gists(token)
        self.auto_find_btn.setEnabled(True)
        
        if not success:
            QMessageBox.critical(self, "错误", f"获取 Gist 列表失败: {error}")
            self.load_status()
            return
            
        gist_info = gist_manager.find_config_gist(gists)
        if gist_info:
            gist_id = gist_info["id"]
            self.gist_id_edit.setText(gist_id)
            self.status_label.setText(f"✅ 已找到配置 Gist: {gist_id}")
            QMessageBox.information(self, "成功", f"已自动发现并填充配置 Gist！\n\nID: {gist_id}\n描述: {gist_info['description']}")
        else:
            QMessageBox.information(self, "未找到", "在您的 Gists 中未找到包含 REPO-GROUPS.md 的配置。")
            self.load_status()

    def open_advanced_manager(self):
        """Open the advanced Gist manager dialog."""
        from .gist_manager_dialog import GistManagerDialog
        dialog = GistManagerDialog(self.parent())
        dialog.exec()
        self.load_status()


__all__ = ["AutoSyncDialog"]
