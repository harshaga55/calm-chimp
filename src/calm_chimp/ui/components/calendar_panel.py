from __future__ import annotations

from datetime import date
from typing import Iterable

from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget, QCalendarWidget

from ...domain import CalendarEvent, EventStatus


_STATUS_COLORS = {
    EventStatus.PLANNED: "#4cc9f0",
    EventStatus.IN_PROGRESS: "#ffb703",
    EventStatus.COMPLETED: "#70e000",
    EventStatus.CANCELED: "#ef233c",
}


class CalendarPanel(QWidget):
    day_changed = pyqtSignal(str)
    event_selected = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("calendarPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.date_label = QLabel("")
        self.date_label.setObjectName("title")
        layout.addWidget(self.date_label)

        self.calendar_widget = QCalendarWidget()
        self.calendar_widget.setGridVisible(False)
        self.calendar_widget.selectionChanged.connect(self._emit_day_change)
        layout.addWidget(self.calendar_widget)

        layout.addWidget(QLabel("Events"))
        self.event_list = QListWidget()
        self.event_list.itemSelectionChanged.connect(self._on_event_selected)
        layout.addWidget(self.event_list, stretch=1)

        self.set_day(date.today())

    def set_day(self, day: date) -> None:
        self.date_label.setText(day.strftime("%A, %d %B %Y"))
        self.calendar_widget.setSelectedDate(QDate(day.year, day.month, day.day))

    def populate_events(self, events: Iterable[CalendarEvent]) -> None:
        self.event_list.clear()
        for event in events:
            label = f"{event.starts_at.strftime('%H:%M')} — {event.title}"
            if event.category and event.category.name:
                label += f"  ·  {event.category.name}"
            item = QListWidgetItem(label)
            color = _STATUS_COLORS.get(event.status, "#f8fafc")
            item.setForeground(QColor(color))
            item.setData(Qt.ItemDataRole.UserRole, event)
            item.setToolTip(event.notes or "")
            self.event_list.addItem(item)

    def _emit_day_change(self) -> None:
        qdate = self.calendar_widget.selectedDate()
        iso = qdate.toString("yyyy-MM-dd")
        self.day_changed.emit(iso)
        self.date_label.setText(qdate.toString("dddd, dd MMMM yyyy"))

    def _on_event_selected(self) -> None:
        item = self.event_list.currentItem()
        if not item:
            return
        self.event_selected.emit(item.data(Qt.ItemDataRole.UserRole))
