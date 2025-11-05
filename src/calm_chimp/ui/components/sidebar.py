from __future__ import annotations

from typing import Iterable, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QLabel,
    QHBoxLayout,
)

from ...domain import Category


class Sidebar(QWidget):
    category_selected = pyqtSignal(object)
    create_category_requested = pyqtSignal()
    refresh_requested = pyqtSignal()
    new_event_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.user_label = QLabel("")
        self.user_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.user_label)

        action_row = QHBoxLayout()
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_requested)
        action_row.addWidget(refresh_button)

        new_event = QPushButton("Add Event")
        new_event.clicked.connect(self.new_event_requested)
        action_row.addWidget(new_event)
        layout.addLayout(action_row)

        layout.addWidget(QLabel("Categories"))
        self.category_list = QListWidget()
        self.category_list.itemSelectionChanged.connect(self._emit_selected_category)
        layout.addWidget(self.category_list, stretch=1)

        add_category = QPushButton("New Category")
        add_category.clicked.connect(self.create_category_requested)
        layout.addWidget(add_category)

        layout.addStretch(1)

    def set_user(self, *, email: str, full_name: Optional[str]) -> None:
        if full_name:
            text = f"<b>{full_name}</b><br><span style='color:#94a3b8'>{email}</span>"
        else:
            text = f"<b>{email}</b>"
        self.user_label.setText(text)

    def set_categories(self, categories: Iterable[Category]) -> None:
        self.category_list.clear()
        for category in categories:
            item = QListWidgetItem(category.name)
            item.setData(Qt.ItemDataRole.UserRole, category)
            color = QColor(category.color or "#4cc9f0")
            item.setForeground(color)
            self.category_list.addItem(item)

    def _emit_selected_category(self) -> None:
        item = self.category_list.currentItem()
        if not item:
            self.category_selected.emit(None)
            return
        self.category_selected.emit(item.data(Qt.ItemDataRole.UserRole))
