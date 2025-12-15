from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppPalette:
    background_primary: str = "#030712"
    background_secondary: str = "#050b18"
    surface: str = "#0c162c"
    surface_alt: str = "#12203f"
    accent_primary: str = "#7dd3fc"
    accent_secondary: str = "#f472b6"
    accent_success: str = "#4ade80"
    accent_warning: str = "#fed34d"
    accent_error: str = "#fb7185"
    text_primary: str = "#f8fafc"
    text_secondary: str = "#c7d2fe"
    border_subtle: str = "#1e293b"
    border_strong: str = "#243657"

    def as_stylesheet(self) -> str:
        """Quick access to a global stylesheet for the PyQt app."""

        return f"""
        QWidget {{
            background-color: {self.background_primary};
            color: {self.text_primary};
            font-family: 'Helvetica Neue', 'Segoe UI', Arial, sans-serif;
            font-size: 14px;
            letter-spacing: 0.15px;
        }}
        QPushButton {{
            background-color: {self.accent_primary};
            color: #031525;
            border: none;
            padding: 10px 16px;
            border-radius: 10px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: #5cc9f5;
        }}
        QPushButton:pressed {{
            padding-top: 11px;
            padding-bottom: 9px;
        }}
        QPushButton:disabled {{
            background-color: {self.border_subtle};
            color: {self.text_secondary};
        }}
        QPushButton#secondaryButton {{
            background-color: transparent;
            color: {self.accent_primary};
            border: 1px solid {self.accent_primary};
        }}
        QPushButton#secondaryButton:hover {{
            background-color: rgba(125, 211, 252, 0.12);
        }}
        QPushButton#googleButton {{
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid rgba(15, 23, 42, 0.18);
            border-radius: 999px;
            font-weight: 600;
            padding: 12px 16px;
        }}
        QPushButton#googleButton:hover {{
            border-color: rgba(15, 23, 42, 0.4);
            background-color: #f8fafc;
        }}
        QLineEdit, QTextEdit, QComboBox, QDateEdit {{
            background-color: {self.background_secondary};
            color: {self.text_primary};
            border: 1px solid {self.border_strong};
            border-radius: 8px;
            padding: 10px 12px;
        }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateEdit:focus {{
            border-color: {self.accent_primary};
        }}
        QListView, QTreeView, QTableView {{
            background-color: {self.background_secondary};
            alternate-background-color: {self.surface};
            border: 1px solid {self.border_strong};
            selection-background-color: rgba(125, 211, 252, 0.25);
            selection-color: {self.background_primary};
        }}
        QDialog#loginDialog {{
            background-color: #040915;
        }}
        QFrame#loginShell {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #081226, stop:1 #0d1b34);
            border-radius: 24px;
            border: 1px solid rgba(148, 163, 184, 0.14);
        }}
        QFrame#loginForm {{
            background-color: rgba(10, 18, 35, 0.94);
            border-radius: 20px;
            border: 1px solid rgba(148, 163, 184, 0.24);
        }}
        QFrame#panel {{
            background-color: {self.surface};
            border: 1px solid {self.border_strong};
            border-radius: 12px;
        }}
        QLabel#heroTitle {{
            font-size: 24px;
            font-weight: 800;
            color: {self.text_primary};
        }}
        QLabel#heroSubtitle {{
            font-size: 14px;
            color: #c4d2f4;
        }}
        QLabel#heroTagline {{
            font-size: 12px;
            color: rgba(148, 163, 184, 0.9);
            letter-spacing: 1px;
            text-transform: uppercase;
        }}
        QLabel#brandLogo {{
            margin: 0;
        }}
        QFrame#logoBadge {{
            background-color: rgba(125, 211, 252, 0.08);
            border: 1px solid rgba(125, 211, 252, 0.28);
            border-radius: 16px;
        }}
        QLabel#brandName {{
            font-size: 16px;
            font-weight: 700;
            color: {self.text_primary};
        }}
        QLabel#brandTagline {{
            font-size: 12px;
            color: rgba(255, 255, 255, 0.65);
        }}
        QFrame#pillRow {{
            background-color: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 12px;
        }}
        QLabel#featurePill {{
            background-color: rgba(125, 211, 252, 0.12);
            color: #dbeafe;
            border: 1px solid rgba(125, 211, 252, 0.35);
            border-radius: 10px;
            padding: 6px 10px;
            font-size: 12px;
            font-weight: 600;
        }}
        QWidget#sidebarPanel {{
            background-color: {self.surface_alt};
            border-right: 1px solid {self.border_strong};
        }}
        QWidget#calendarPanel, QWidget#chatPanel {{
            background-color: {self.surface};
        }}
        QSplitter::handle {{
            background: {self.border_strong};
            width: 2px;
        }}
        QTextEdit#chatTranscript {{
            background-color: {self.background_secondary};
            border: 1px solid {self.border_strong};
            border-radius: 12px;
            padding: 12px;
        }}
        """
