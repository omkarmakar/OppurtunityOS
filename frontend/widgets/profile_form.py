"""Targeting form widget — edit slot-level targeting fields."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from frontend.theme import (
    ACCENT,
    BORDER_SUBTLE,
    TEXT_BRIGHT,
    TEXT_SECONDARY,
    card_frame_stylesheet,
    muted_label_stylesheet,
)


class TagInput(QWidget):
    """A tag/chip input widget for lists of strings."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tags: list[str] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        input_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type and press Enter...")
        self._input.returnPressed.connect(self._add_tag)
        add_btn = QPushButton("+")
        add_btn.setFixedWidth(28)
        add_btn.clicked.connect(self._add_tag)
        input_row.addWidget(self._input, 1)
        input_row.addWidget(add_btn)
        layout.addLayout(input_row)

        self._list = QListWidget()
        self._list.setMaximumHeight(80)
        self._list.setStyleSheet("QListWidget { font-size: 11px; }")
        layout.addWidget(self._list)

    def _add_tag(self) -> None:
        text = self._input.text().strip()
        if text and text not in self._tags:
            self._tags.append(text)
            item = QListWidgetItem(f"  {text}  \u2716")
            self._list.addItem(item)
        self._input.clear()

    def set_tags(self, tags: list[str]) -> None:
        self._tags = []
        self._list.clear()
        for t in tags:
            self._tags.append(t)
            self._list.addItem(QListWidgetItem(f"  {t}  \u2716"))

    def get_tags(self) -> list[str]:
        return list(self._tags)

    def mousePressEvent(self, event) -> None:
        list_pos = self._list.mapFrom(self, event.position().toPoint())
        item = self._list.itemAt(list_pos)
        if item and "\u2716" in item.text():
            rect = self._list.visualItemRect(item)
            if list_pos.x() >= rect.right() - 24:
                idx = self._list.row(item)
                self._list.takeItem(idx)
                if idx < len(self._tags):
                    self._tags.pop(idx)
                return
        super().mousePressEvent(event)


class TargetingForm(QWidget):
    """Form for editing slot-level targeting fields.

    Editable fields: slot name, preferred locations, remote preference,
    salary expectations, target companies.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slot_id: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._build_save_button(layout)

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        self._build_name_inline(row1)
        self._build_remote_inline(row1)
        self._build_salary_inline(row1)
        layout.addLayout(row1)

        self._build_locations(layout)
        self._build_companies(layout)

    def _field_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("targetFieldCard")
        card.setStyleSheet(card_frame_stylesheet("targetFieldCard"))
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(4)
        label = QLabel(title)
        label.setStyleSheet(muted_label_stylesheet(size=11, weight=600))
        card_layout.addWidget(label)
        return card, card_layout

    def _build_name_inline(self, parent_layout: QHBoxLayout) -> None:
        card, cl = self._field_card("Slot Name")
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. R&D Track")
        cl.addWidget(self._name)
        parent_layout.addWidget(card, 2)

    def _build_remote_inline(self, parent_layout: QHBoxLayout) -> None:
        card, cl = self._field_card("Remote")
        self._remote = QComboBox()
        self._remote.addItems(["", "remote", "hybrid", "on-site"])
        self._remote.setStyleSheet(f"""
            QComboBox {{
                background-color: #222238; color: {TEXT_BRIGHT};
                border: 1px solid {BORDER_SUBTLE}; border-radius: 6px;
                padding: 4px 8px; font-size: 12px;
            }}
            QComboBox:hover {{ background-color: #2c2c48; }}
            QComboBox QAbstractItemView {{
                background-color: #1a1a2e; color: {TEXT_BRIGHT};
                selection-background-color: {ACCENT};
            }}
        """)
        cl.addWidget(self._remote)
        parent_layout.addWidget(card, 1)

    def _build_salary_inline(self, parent_layout: QHBoxLayout) -> None:
        card, cl = self._field_card("Salary")
        self._salary = QLineEdit()
        self._salary.setPlaceholderText("e.g. 120k-150k")
        cl.addWidget(self._salary)
        parent_layout.addWidget(card, 1)

    def _build_locations(self, parent_layout: QVBoxLayout) -> None:
        card, cl = self._field_card("Preferred Locations")
        self._locations = TagInput()
        self._locations.setMaximumHeight(100)
        cl.addWidget(self._locations)
        parent_layout.addWidget(card)

    def _build_companies(self, parent_layout: QVBoxLayout) -> None:
        card, cl = self._field_card("Target Companies")
        self._companies = TagInput()
        self._companies.setMaximumHeight(100)
        cl.addWidget(self._companies)
        parent_layout.addWidget(card)

    def _build_save_button(self, parent_layout: QVBoxLayout) -> None:
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 4)
        btn_row.addStretch()
        self._save_btn = QPushButton("Save Profile")
        self._save_btn.setObjectName("primaryButton")
        self._save_btn.setStyleSheet(f"""
            QPushButton#primaryButton {{
                background-color: {ACCENT}; color: white; border: none;
                border-radius: 6px; padding: 7px 20px;
                font-size: 13px; font-weight: 700;
            }}
            QPushButton#primaryButton:hover {{ background-color: #6d28d9; }}
        """)
        self._save_btn.clicked.connect(self._save)
        btn_row.addWidget(self._save_btn)
        parent_layout.addLayout(btn_row)

    def set_slot_id(self, slot_id: str | None) -> None:
        self._slot_id = slot_id

    def get_slot_id(self) -> str | None:
        return self._slot_id

    def populate(self, data: dict[str, Any]) -> None:
        self._name.setText(data.get("name") or "")
        self._salary.setText(data.get("salary_expectations") or "")
        self._locations.set_tags(data.get("preferred_locations") or [])
        self._companies.set_tags(data.get("target_companies") or [])
        remote = data.get("remote_preference") or ""
        idx = self._remote.findText(remote)
        self._remote.setCurrentIndex(idx if idx >= 0 else 0)

    def collect(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        name = self._name.text().strip()
        if name:
            data["name"] = name
        salary = self._salary.text().strip()
        if salary:
            data["salary_expectations"] = salary
        locs = self._locations.get_tags()
        if locs:
            data["preferred_locations"] = locs
        companies = self._companies.get_tags()
        if companies:
            data["target_companies"] = companies
        remote = self._remote.currentText().strip()
        if remote:
            data["remote_preference"] = remote
        return data

    def clear(self) -> None:
        self._name.clear()
        self._salary.clear()
        self._locations.set_tags([])
        self._companies.set_tags([])
        self._remote.setCurrentIndex(0)
        self._slot_id = None

    def _save(self) -> None:
        import httpx
        from PySide6.QtWidgets import QMessageBox

        data = self.collect()
        if not data.get("name"):
            QMessageBox.warning(self, "Validation", "Slot name is required.")
            return

        try:
            if self._slot_id:
                resp = httpx.put(
                    f"http://127.0.0.1:8000/api/v1/profiles/id/{self._slot_id}",
                    json=data, timeout=10,
                )
                resp.raise_for_status()
                saved = resp.json()
                self.populate(saved)
                QMessageBox.information(self, "Saved", "Slot targeting updated.")
            else:
                from frontend.user_context import get_active_user_id

                data["user_id"] = get_active_user_id()
                resp = httpx.post(
                    "http://127.0.0.1:8000/api/v1/profiles",
                    json=data, timeout=10,
                )
                resp.raise_for_status()
                saved = resp.json()
                self._slot_id = saved.get("id")
                self.populate(saved)
                QMessageBox.information(self, "Created", "New slot created.")
        except httpx.HTTPError as e:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")
