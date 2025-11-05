from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QTextEdit, QVBoxLayout


class CategoryDialog(QDialog):
    def __init__(self, *, name: str = "", color: str = "", icon: str = "", description: str = "") -> None:
        super().__init__()
        self.setWindowTitle("Category")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit(name)
        form.addRow("Name", self.name_input)

        self.color_input = QLineEdit(color)
        self.color_input.setPlaceholderText("#4cc9f0")
        form.addRow("Color", self.color_input)

        self.icon_input = QLineEdit(icon)
        self.icon_input.setPlaceholderText("emoji or icon name (optional)")
        form.addRow("Icon", self.icon_input)

        self.description_input = QTextEdit(description)
        self.description_input.setPlaceholderText("Optional description")
        form.addRow("Description", self.description_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict[str, Optional[str]]:
        return {
            "name": self.name_input.text().strip(),
            "color": self.color_input.text().strip() or None,
            "icon": self.icon_input.text().strip() or None,
            "description": self.description_input.toPlainText().strip(),
        }
