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
        }}
        QPushButton:disabled {{
            background-color: {self.border_subtle};
            color: {self.text_secondary};
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
        QLabel#title {{
            font-size: 22px;
            font-weight: 600;
            color: {self.accent_primary};
        }}
        QLabel#subtitle {{
            font-size: 16px;
            color: {self.text_secondary};
        }}
        """
