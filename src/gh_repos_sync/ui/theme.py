"""UI theme styles."""


def build_custom_stylesheet(scale: float = 1.0) -> str:
    """Build stylesheet with scalable typography metrics."""

    def px(value: float) -> int:
        return max(1, int(round(value * scale)))

    font_boost = 1.10

    def pt(value: float) -> int:
        return max(1, int(round(value * scale * font_boost)))

    return f"""
    QWidget {{
        background-color: #1e1e1e;
        color: #e6e6e6;
        font-family: "Segoe UI";
        font-size: {pt(10)}pt;
    }}
    QLabel#section-title {{
        color: #f0f0f0;
        font-size: {pt(12)}pt;
        font-weight: bold;
    }}
    QLabel#app-title {{
        color: #f5f5f5;
        font-size: {pt(14)}pt;
        font-weight: 700;
        padding-bottom: {px(2)}px;
    }}
    QLabel#section-subtitle {{
        color: #bdbdbd;
        font-size: {pt(9)}pt;
    }}
    QLabel#app-subtitle {{
        color: #bdbdbd;
        font-size: {pt(9.5)}pt;
    }}
    QLineEdit, QTextEdit, QListWidget {{
        background-color: #242424;
        border: 1px solid #3a3a3a;
        border-radius: {px(6)}px;
        padding: {px(6)}px;
        selection-background-color: #3d5a80;
    }}
    QSpinBox {{
        background-color: #242424;
        border: 1px solid #3a3a3a;
        border-radius: {px(6)}px;
        selection-background-color: #3d5a80;
        padding-top: 0px;
        padding-bottom: 0px;
        padding-left: {px(12)}px;
        padding-right: {px(34)}px;
        font-size: {pt(11)}pt;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        width: {px(24)}px;
        border: none;
        background: transparent;
    }}
    QPushButton {{
        background-color: #2c2c2c;
        border: 1px solid #3a3a3a;
        border-radius: {px(6)}px;
        padding: {px(6)}px {px(14)}px;
        min-height: {px(30)}px;
        font-size: {pt(10.5)}pt;
    }}
    QPushButton:hover {{
        background-color: #333333;
    }}
    QPushButton:disabled {{
        background-color: #2a2a2a;
        color: #777;
    }}
    QProgressBar {{
        border: 1px solid #3a3a3a;
        border-radius: {px(6)}px;
        text-align: center;
        background-color: #242424;
    }}
    QProgressBar::chunk {{
        background-color: #4d7c8a;
        border-radius: {px(6)}px;
    }}
    QFrame#divider {{
        background-color: #3a3a3a;
        max-height: 1px;
        min-height: 1px;
    }}
"""


CUSTOM_STYLESHEET = build_custom_stylesheet(1.0)
