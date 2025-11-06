from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppPalette:
    background_primary: str = "#101926"
    background_secondary: str = "#162437"
    surface: str = "#1f2f47"
    accent_primary: str = "#4cc9f0"
    accent_secondary: str = "#f72585"
    accent_success: str = "#70e000"
    accent_warning: str = "#ffb703"
    accent_error: str = "#ef233c"
    text_primary: str = "#f8fafc"
    text_secondary: str = "#cbd5f5"
    border_subtle: str = "#1e293b"

    def as_stylesheet(self) -> str:
        """Quick access to a global stylesheet for the PyQt app."""

        return f"""
        QWidget {{
            background-color: {self.background_primary};
            color: {self.text_primary};
            font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
            font-size: 14px;
        }}
        QPushButton {{
            background-color: {self.accent_primary};
            color: {self.background_primary};
            border: none;
            padding: 10px 16px;
            border-radius: 8px;
            font-weight: 600;
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
            background-color: rgba(76, 201, 240, 0.12);
        }}
        QPushButton#googleButton {{
            background-color: {self.background_secondary};
            color: {self.text_primary};
            border: 1px solid {self.border_subtle};
        }}
        QPushButton#googleButton:hover {{
            border-color: {self.accent_primary};
        }}
        QLineEdit, QTextEdit, QComboBox, QDateEdit {{
            background-color: {self.background_secondary};
            color: {self.text_primary};
            border: 1px solid {self.border_subtle};
            border-radius: 6px;
            padding: 8px 10px;
        }}
        QListView, QTreeView, QTableView {{
            background-color: {self.background_secondary};
            alternate-background-color: {self.surface};
            border: 1px solid {self.border_subtle};
            selection-background-color: {self.accent_secondary};
            selection-color: {self.background_primary};
        }}
        QFrame#loginCard {{
            background-color: {self.surface};
            border-radius: 20px;
            border: 1px solid {self.border_subtle};
        }}
        QFrame#divider {{
            background-color: {self.border_subtle};
            border: none;
            min-height: 1px;
            max-height: 1px;
        }}
        QLabel#title {{
            font-size: 22px;
            font-weight: 600;
            color: {self.accent_primary};
        }}
        QLabel#subtitle {{
            font-size: 16px;
            color: {self.text_secondary};
        }}
        QLabel#caption {{
            font-size: 13px;
            color: {self.text_secondary};
        }}
        QLabel#muted {{
            font-size: 12px;
            color: {self.text_secondary};
        }}
        """
