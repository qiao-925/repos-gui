"""Gist configuration management dialog."""

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QVBoxLayout, QCheckBox, QComboBox, QProgressBar,
    QMessageBox, QFileDialog, QSplitter, QWidget
)

from ..core.repo_config import (
    create_gist_from_config, get_gist_cache_info, load_config_from_gist,
    save_config_to_gist, sync_config_from_gist, clear_gist_cache
)
from ..infra.gist_config import gist_manager
from ..infra.logger import log_error, log_info, log_success, log_warning


class GistWorker(QThread):
    """Worker for Gist operations."""
    
    success = pyqtSignal(str, str)  # operation, result
    error = pyqtSignal(str, str)    # operation, error
    progress = pyqtSignal(str)      # status message
    
    def __init__(self, operation: str, **kwargs):
        super().__init__()
        self.operation = operation
        self.kwargs = kwargs
    
    def run(self):
        try:
            if self.operation == "download":
                self.progress.emit("正在从 Gist 下载配置...")
                success, content, error = load_config_from_gist(**self.kwargs)
                if success:
                    self.success.emit(self.operation, content)
                else:
                    self.error.emit(self.operation, error)
            
            elif self.operation == "upload":
                self.progress.emit("正在上传配置到 Gist...")
                success, error = save_config_to_gist(**self.kwargs)
                if success:
                    self.success.emit(self.operation, "上传成功")
                else:
                    self.error.emit(self.operation, error)
            
            elif self.operation == "create":
                self.progress.emit("正在创建新的 Gist...")
                success, gist_id, gist_url = create_gist_from_config(**self.kwargs)
                if success:
                    self.success.emit(self.operation, f"{gist_id}|{gist_url}")
                else:
                    self.error.emit(self.operation, gist_id or "创建失败")
            
            elif self.operation == "sync":
                self.progress.emit("正在同步配置...")
                success, error = sync_config_from_gist(**self.kwargs)
                if success:
                    self.success.emit(self.operation, "同步成功")
                else:
                    self.error.emit(self.operation, error)
            
            elif self.operation == "validate":
                self.progress.emit("正在验证 Gist URL...")
                success, gist_id_or_error = gist_manager.validate_gist_url(self.kwargs.get("url", ""))
                if success:
                    self.success.emit(self.operation, gist_id_or_error)
                else:
                    self.error.emit(self.operation, gist_id_or_error)
        
        except Exception as e:
            self.error.emit(self.operation, f"操作异常: {e}")


class GistManagerDialog(QDialog):
    """Dialog for managing Gist configurations."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GitHub Gist 配置管理")
        self.setModal(True)
        self.resize(800, 600)
        
        self.worker = None
        self.init_ui()
        self.load_cache_info()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Gist URL 输入区域
        url_group = QGroupBox("Gist 配置")
        url_layout = QFormLayout()
        
        self.gist_url_edit = QLineEdit()
        self.gist_url_edit.setPlaceholderText("https://gist.github.com/username/gist_id")
        self.validate_btn = QPushButton("验证")
        self.validate_btn.clicked.connect(self.validate_gist_url)
        
        url_layout.addRow("Gist URL:", self.gist_url_edit)
        url_layout.addRow("", self.validate_btn)
        url_group.setLayout(url_layout)
        
        # GitHub Token 输入
        token_group = QGroupBox("GitHub 认证")
        token_layout = QFormLayout()
        
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("可选，用于私有 Gist 或提高限制")
        
        token_layout.addRow("GitHub Token:", self.token_edit)
        token_group.setLayout(token_layout)
        
        # 操作按钮
        action_group = QGroupBox("操作")
        action_layout = QHBoxLayout()
        
        self.download_btn = QPushButton("从 Gist 下载")
        self.upload_btn = QPushButton("上传到 Gist")
        self.sync_btn = QPushButton("同步配置")
        self.create_btn = QPushButton("创建新 Gist")
        
        self.download_btn.clicked.connect(self.download_from_gist)
        self.upload_btn.clicked.connect(self.upload_to_gist)
        self.sync_btn.clicked.connect(self.sync_from_gist)
        self.create_btn.clicked.connect(self.create_new_gist)
        
        action_layout.addWidget(self.download_btn)
        action_layout.addWidget(self.upload_btn)
        action_layout.addWidget(self.sync_btn)
        action_layout.addWidget(self.create_btn)
        action_group.setLayout(action_layout)
        
        # 预览区域
        preview_group = QGroupBox("配置预览")
        preview_layout = QVBoxLayout()
        
        self.preview_text = QTextEdit()
        self.preview_text.setFont(QFont("Consolas", 10))
        self.preview_text.setReadOnly(True)
        
        preview_layout.addWidget(self.preview_text)
        preview_group.setLayout(preview_layout)
        
        # 缓存信息
        cache_group = QGroupBox("缓存信息")
        cache_layout = QVBoxLayout()
        
        self.cache_info_label = QLabel("暂无缓存信息")
        self.clear_cache_btn = QPushButton("清理缓存")
        self.clear_cache_btn.clicked.connect(self.clear_cache)
        
        cache_layout.addWidget(self.cache_info_label)
        cache_layout.addWidget(self.clear_cache_btn)
        cache_group.setLayout(cache_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        
        # 添加到主布局
        layout.addWidget(url_group)
        layout.addWidget(action_group)
        layout.addWidget(preview_group)
        layout.addWidget(cache_group)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def validate_gist_url(self):
        """Validate Gist URL."""
        url = self.gist_url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "警告", "请输入 Gist URL")
            return
        
        self.start_worker("validate", url=url)
    
    def download_from_gist(self):
        """Download configuration from Gist."""
        gist_id = self.extract_gist_id()
        if not gist_id:
            return
        
        self.start_worker("download", gist_id=gist_id)
    
    def upload_to_gist(self):
        """Upload configuration to Gist."""
        gist_id = self.extract_gist_id()
        if not gist_id:
            return
        
        self.start_worker("upload", gist_id=gist_id)
    
    def sync_from_gist(self):
        """Sync configuration from Gist."""
        gist_id = self.extract_gist_id()
        if not gist_id:
            return
        
        self.start_worker("sync", gist_id=gist_id)
    
    def create_new_gist(self):
        """Create a new Gist."""
        # 询问是否公开
        public = QMessageBox.question(
            self, "选择类型", 
            "创建公开的 Gist 还是私有的 Gist？\n\n公开：任何人可见\n私有：仅自己可见",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        ) == QMessageBox.Yes
        
        self.start_worker("create", public=public)
    
    def extract_gist_id(self):
        """Extract Gist ID from URL."""
        url = self.gist_url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "警告", "请输入 Gist URL")
            return None
        
        success, result = gist_manager.validate_gist_url(url)
        if not success:
            QMessageBox.warning(self, "错误", f"无效的 Gist URL: {result}")
            return None
        
        return result
    
    def start_worker(self, operation: str, **kwargs):
        """Start a worker operation."""
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "警告", "另一个操作正在进行中")
            return
        
        self.worker = GistWorker(operation, **kwargs)
        self.worker.progress.connect(self.on_progress)
        self.worker.success.connect(self.on_success)
        self.worker.error.connect(self.on_error)
        self.worker.start()
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        self.set_ui_enabled(False)
    
    def on_progress(self, message: str):
        """Handle progress updates."""
        self.status_label.setText(message)
    
    def on_success(self, operation: str, result: str):
        """Handle successful operations."""
        self.progress_bar.setVisible(False)
        self.status_label.setText("操作完成")
        self.set_ui_enabled(True)
        
        if operation == "download":
            self.preview_text.setPlainText(result)
            QMessageBox.information(self, "成功", "配置下载成功，请查看预览")
        
        elif operation == "upload":
            QMessageBox.information(self, "成功", "配置上传成功")
        
        elif operation == "create":
            parts = result.split("|")
            if len(parts) == 2:
                gist_id, gist_url = parts
                self.gist_url_edit.setText(gist_url)
                QMessageBox.information(self, "成功", f"Gist 创建成功\n\nURL: {gist_url}")
        
        elif operation == "sync":
            QMessageBox.information(self, "成功", "配置同步成功")
        
        elif operation == "validate":
            self.status_label.setText(f"Gist 验证成功: {result}")
        
        self.load_cache_info()
    
    def on_error(self, operation: str, error: str):
        """Handle operation errors."""
        self.progress_bar.setVisible(False)
        self.status_label.setText("操作失败")
        self.set_ui_enabled(True)
        QMessageBox.critical(self, "错误", f"操作失败: {error}")
    
    def set_ui_enabled(self, enabled: bool):
        """Enable/disable UI elements."""
        self.gist_url_edit.setEnabled(enabled)
        self.validate_btn.setEnabled(enabled)
        self.download_btn.setEnabled(enabled)
        self.upload_btn.setEnabled(enabled)
        self.sync_btn.setEnabled(enabled)
        self.create_btn.setEnabled(enabled)
        self.clear_cache_btn.setEnabled(enabled)
    
    def load_cache_info(self):
        """Load and display cache information."""
        cache_info = get_gist_cache_info()
        if not cache_info:
            self.cache_info_label.setText("暂无缓存信息")
            return
        
        text = "已缓存的配置:\n\n"
        for key, info in cache_info.items():
            gist_id = info.get("gist_id", "")
            filename = info.get("filename", "")
            timestamp = info.get("timestamp", 0)
            
            from datetime import datetime
            time_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            
            text += f"Gist: {gist_id}\n"
            text += f"文件: {filename}\n"
            text += f"缓存时间: {time_str}\n\n"
        
        self.cache_info_label.setText(text)
    
    def clear_cache(self):
        """Clear Gist cache."""
        reply = QMessageBox.question(
            self, "确认", "确定要清理所有 Gist 缓存吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            clear_gist_cache()
            self.load_cache_info()
            QMessageBox.information(self, "成功", "缓存已清理")
    
    def closeEvent(self, event):
        """Handle dialog close event."""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "确认", "操作正在进行中，确定要关闭吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                event.ignore()
                return
            
            # 强制停止工作线程
            self.worker.terminate()
            self.worker.wait()
        
        event.accept()


__all__ = ["GistManagerDialog"]
