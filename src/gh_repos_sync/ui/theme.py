"""UI theme styles."""

CUSTOM_STYLESHEET = """
    QWidget {
        background-color: #1e1e1e;
        color: #e6e6e6;
        font-family: "Segoe UI";
        font-size: 10pt;
    }
    QLabel#section-title {
        color: #f0f0f0;
        font-size: 12pt;
        font-weight: bold;
    }
    QLabel#app-title {
        color: #f5f5f5;
        font-size: 14pt;
        font-weight: 700;
        padding-bottom: 2px;
    }
    QLabel#section-subtitle {
        color: #bdbdbd;
        font-size: 9pt;
    }
    QLabel#app-subtitle {
        color: #bdbdbd;
        font-size: 9.5pt;
    }
    QLineEdit, QTextEdit, QListWidget, QSpinBox {
        background-color: #242424;
        border: 1px solid #3a3a3a;
        border-radius: 6px;
        padding: 6px;
        selection-background-color: #3d5a80;
    }
    QPushButton {
        background-color: #2c2c2c;
        border: 1px solid #3a3a3a;
        border-radius: 6px;
        padding: 6px 14px;
        min-height: 30px;
        font-size: 10.5pt;
    }
    QPushButton:hover {
        background-color: #333333;
    }
    QPushButton:disabled {
        background-color: #2a2a2a;
        color: #777;
    }
    QProgressBar {
        border: 1px solid #3a3a3a;
        border-radius: 6px;
        text-align: center;
        background-color: #242424;
    }
    QProgressBar::chunk {
        background-color: #4d7c8a;
        border-radius: 6px;
    }
    QFrame#divider {
        background-color: #3a3a3a;
        max-height: 1px;
        min-height: 1px;
    }
"""
