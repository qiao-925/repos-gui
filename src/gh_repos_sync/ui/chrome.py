"""Window chrome helpers (icon/titlebar/section widgets)."""

import ctypes
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel


def build_app_icon() -> QIcon:
    """Build in-memory app icon with `GH` badge."""
    icon_size = 64
    pixmap = QPixmap(icon_size, icon_size)
    pixmap.fill(QColor("#1e1e1e"))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#4d7c8a"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(6, 6, 52, 52, 10, 10)

    painter.setPen(QColor("#f0f0f0"))
    painter.setFont(QFont("Segoe UI", 18, QFont.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "GH")
    painter.end()

    return QIcon(pixmap)


def apply_windows_dark_titlebar(window) -> None:
    """Enable Windows dark titlebar if available."""
    if sys.platform != "win32":
        return

    try:
        hwnd = int(window.winId())
        dark_mode = ctypes.c_int(1)
        for attr in (20, 19):
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                attr,
                ctypes.byref(dark_mode),
                ctypes.sizeof(dark_mode),
            )
            if result == 0:
                return
    except Exception:
        return


def make_section_header(title: str) -> QHBoxLayout:
    """Create a section title + divider row."""
    layout = QHBoxLayout()
    label = QLabel(title)
    label.setObjectName("section-title")
    layout.addWidget(label)

    line = QFrame()
    line.setObjectName("divider")
    line.setFrameShape(QFrame.HLine)
    layout.addWidget(line, 1)
    return layout

