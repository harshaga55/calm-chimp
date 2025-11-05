from __future__ import annotations

from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QApplication

from ...config import AppPalette


def apply_palette(app: QApplication, palette: AppPalette) -> None:
    qt_palette = QPalette()
    qt_palette.setColor(QPalette.ColorRole.Window, QColor(palette.background_primary))
    qt_palette.setColor(QPalette.ColorRole.Base, QColor(palette.background_secondary))
    qt_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(palette.surface))
    qt_palette.setColor(QPalette.ColorRole.Text, QColor(palette.text_primary))
    qt_palette.setColor(QPalette.ColorRole.WindowText, QColor(palette.text_primary))
    qt_palette.setColor(QPalette.ColorRole.Button, QColor(palette.accent_primary))
    qt_palette.setColor(QPalette.ColorRole.ButtonText, QColor(palette.background_primary))
    qt_palette.setColor(QPalette.ColorRole.Highlight, QColor(palette.accent_secondary))
    qt_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(palette.background_primary))
    app.setPalette(qt_palette)
    app.setStyleSheet(palette.as_stylesheet())
