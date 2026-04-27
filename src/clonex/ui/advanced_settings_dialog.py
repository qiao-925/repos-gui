"""Advanced settings dialog to hide complexity from the main window.

Two tabs: concurrency parameters and Gist sync entry points.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, 
    QWidget, QPushButton, QLabel, QFormLayout, QSpinBox
)

class AdvancedSettingsDialog(QDialog):
    """Dialog for advanced configuration (concurrency and Gist sync)."""
    
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setWindowTitle("高级设置 (Advanced)")
        self.resize(500, 420)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        tabs = QTabWidget()
        
        # --- Tab 1: 并发与执行 ---
        exec_tab = QWidget()
        exec_layout = QFormLayout()
        exec_layout.setVerticalSpacing(15)
        
        exec_desc = QLabel("调整批量操作时的并发参数。\n如果遇到网络风控或限流，请适当降低并发数。")
        exec_desc.setStyleSheet("color: #888;")
        exec_layout.addRow(exec_desc)
        
        self.tasks_spin = QSpinBox()
        self.tasks_spin.setRange(1, 64)
        self.tasks_spin.setValue(self.parent_window.parallel_tasks)
        self.tasks_spin.setMinimumHeight(32)
        
        self.connections_spin = QSpinBox()
        self.connections_spin.setRange(1, 64)
        self.connections_spin.setValue(self.parent_window.parallel_connections)
        self.connections_spin.setMinimumHeight(32)
        
        exec_layout.addRow("并行任务数 (Tasks):", self.tasks_spin)
        exec_layout.addRow("并行连接数 (Connections):", self.connections_spin)
        
        exec_tab.setLayout(exec_layout)
        tabs.addTab(exec_tab, "并发设置")
        
        # --- Tab 2: 云端同步 ---
        gist_tab = QWidget()
        gist_layout = QVBoxLayout()
        gist_layout.setSpacing(12)
        
        gist_desc = QLabel("使用 GitHub Gist 在多台设备间同步您的分组配置文件 (REPO-GROUPS.md)。")
        gist_desc.setWordWrap(True)
        gist_layout.addWidget(gist_desc)
        
        auto_sync_btn = QPushButton("自动同步设置...")
        auto_sync_btn.setMinimumHeight(34)
        auto_sync_btn.clicked.connect(self.parent_window.open_auto_sync_settings)
        
        gist_manager_btn = QPushButton("Gist 管理器 (手动介入)...")
        gist_manager_btn.setMinimumHeight(34)
        gist_manager_btn.clicked.connect(self.parent_window.open_gist_manager)
        
        gist_layout.addWidget(auto_sync_btn)
        gist_layout.addWidget(gist_manager_btn)
        gist_layout.addStretch(1)
        gist_tab.setLayout(gist_layout)
        tabs.addTab(gist_tab, "云端同步 (Gist)")

        layout.addWidget(tabs)
        
        # --- 底部按钮 ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        save_btn = QPushButton("确定")
        save_btn.setMinimumWidth(100)
        save_btn.setMinimumHeight(32)
        save_btn.clicked.connect(self.save_and_close)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def save_and_close(self):
        """Save parallel settings and close."""
        self.parent_window.parallel_tasks = self.tasks_spin.value()
        self.parent_window.parallel_connections = self.connections_spin.value()
        self.accept()
