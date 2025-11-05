from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from PyQt6.QtCore import QDateTime
from PyQt6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
)

from ...domain import Category


class EventDialog(QDialog):
    def __init__(
        self,
        *,
        categories: Iterable[Category],
        default_start: datetime,
        default_end: datetime,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Event")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Title")
        form.addRow("Title", self.title_input)

        self.start_input = QDateTimeEdit()
        self.start_input.setCalendarPopup(True)
        self.start_input.setDateTime(QDateTime(default_start))
        form.addRow("Start", self.start_input)

        self.end_input = QDateTimeEdit()
        self.end_input.setCalendarPopup(True)
        self.end_input.setDateTime(QDateTime(default_end))
        form.addRow("End", self.end_input)

        self.category_box = QComboBox()
        self.category_box.addItem("No category", None)
        for category in categories:
            self.category_box.addItem(category.name, category)
        form.addRow("Category", self.category_box)

        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("Optional location")
        form.addRow("Location", self.location_input)

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Notes")
        form.addRow("Notes", self.notes_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict[str, Optional[str]]:
        start = self.start_input.dateTime().toPyDateTime()
        end = self.end_input.dateTime().toPyDateTime()
        category = self.category_box.currentData()
        category_id = category.id if category else None
        return {
            "title": self.title_input.text().strip(),
            "starts_at": start,
            "ends_at": end,
            "category_id": category_id,
            "notes": self.notes_input.toPlainText().strip(),
            "location": self.location_input.text().strip() or None,
        }
