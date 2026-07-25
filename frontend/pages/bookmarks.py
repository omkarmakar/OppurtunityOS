"""Bookmarks page — list of bookmarked opportunities with inline notes editing."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from frontend.pages.base import PageWidget
from frontend.user_context import get_active_user_id
from frontend.widgets.opportunity_card import TEXT_BRIGHT, TEXT_MUTED

ACCENT = "#7c3aed"
BG_CARD = "#1a1a2e"
RED = "#ef4444"

API_BASE = "http://127.0.0.1:8000/api/v1"


class BookmarkRow(QFrame):
    """A single bookmark row with opportunity info, inline notes editing, and remove button."""

    def __init__(
        self,
        data: dict[str, Any],
        on_remove: callable | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._data = data
        self._bm_id = data.get("id", "")
        self._on_remove = on_remove
        self.setObjectName("bmRow")
        score = data.get("relevance_score")
        score_color = "#10b981" if score and score >= 70 else ("#f59e0b" if score and score >= 40 else "#ef4444")
        self.setStyleSheet(f"""
            QFrame#bmRow {{
                background-color: {BG_CARD}; border-radius: 8px;
                border-left: 3px solid {score_color}; padding: 0px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        self._build_header(layout, score, score_color)
        self._build_notes(layout)
        self._build_actions(layout)

    def _build_header(self, layout: QVBoxLayout, score: float | None, score_color: str) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)

        title = self._data.get("opportunity_title", "Untitled")
        url = self._data.get("opportunity_url", "")
        title_label = QLabel(title[:80])
        title_label.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_BRIGHT}; background: transparent;")
        if url:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            title_label.setCursor(Qt.CursorShape.PointingHandCursor)
            title_label.mousePressEvent = lambda _: QDesktopServices.openUrl(QUrl(url))
        row.addWidget(title_label, 1)

        score_text = f"{int(score)}" if score is not None else "—"
        score_badge = QLabel(score_text)
        score_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_badge.setFixedSize(44, 28)
        score_badge.setStyleSheet(f"""
            QLabel {{
                font-size: 13px; font-weight: 700; color: white;
                background-color: {score_color}; border-radius: 14px;
            }}
        """)
        row.addWidget(score_badge)

        layout.addLayout(row)

    def _build_notes(self, layout: QVBoxLayout) -> None:
        notes_row = QHBoxLayout()
        notes_row.setSpacing(8)

        notes_lbl = QLabel("Notes:")
        notes_lbl.setStyleSheet(f"font-size: 12px; font-weight: 500; color: {TEXT_MUTED}; background: transparent;")
        notes_row.addWidget(notes_lbl)

        self._notes_input = QLineEdit()
        self._notes_input.setText(self._data.get("notes") or "")
        self._notes_input.setPlaceholderText("Add notes...")
        self._notes_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: 1px solid #3a3a5e;
                border-radius: 6px; padding: 6px 10px; font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        self._notes_input.editingFinished.connect(self._save_notes)
        notes_row.addWidget(self._notes_input, 1)

        self._notes_status = QLabel("")
        self._notes_status.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;")
        notes_row.addWidget(self._notes_status)

        layout.addLayout(notes_row)

    def _build_actions(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch()

        remove_btn = QPushButton("Remove")
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #3a1a1a; color: {RED}; border: none;
                border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #4a2a2a; }}
        """)
        remove_btn.clicked.connect(self._remove)
        row.addWidget(remove_btn)

        layout.addLayout(row)

    def _save_notes(self) -> None:
        try:
            resp = httpx.patch(
                f"{API_BASE}/bookmarks/{self._bm_id}",
                json={"notes": self._notes_input.text()},
                timeout=10,
            )
            if resp.status_code == 200:
                self._notes_status.setText("saved")
                QTimer.singleShot(2000, lambda: self._notes_status.setText(""))
        except Exception:
            self._notes_status.setText("error")

    def _remove(self) -> None:
        try:
            resp = httpx.delete(f"{API_BASE}/bookmarks/{self._bm_id}", timeout=10)
            if resp.status_code == 204 and self._on_remove:
                self._on_remove(self._bm_id)
        except Exception:
            pass


class BookmarksPage(PageWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        self._data: dict[str, Any] = {}
        self._page = 1
        self._page_size = 10
        super().__init__("Bookmarks", parent)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        layout.addWidget(scroll)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        scroll.setWidget(container)

        self._main_layout = QVBoxLayout(container)
        self._main_layout.setContentsMargins(32, 32, 32, 32)
        self._main_layout.setSpacing(16)

        self._build_header()
        self._build_card_list()
        self._build_pagination()
        self._main_layout.addStretch()

        self._load_data()

    def _build_header(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)

        title = QLabel("Bookmarks")
        title.setStyleSheet(f"font-size: 24px; font-weight: 600; color: {TEXT_BRIGHT}; background: transparent;")
        row.addWidget(title)

        self._result_count_label = QLabel("")
        self._result_count_label.setStyleSheet(f"font-size: 13px; color: {TEXT_MUTED}; background: transparent;")
        row.addWidget(self._result_count_label)

        row.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 8px 16px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #3a3a5e; }}
        """)
        refresh_btn.clicked.connect(self._load_data)
        row.addWidget(refresh_btn)

        self._main_layout.addLayout(row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("QFrame { color: #2a2a44; max-height: 1px; }")
        self._main_layout.addWidget(sep)

    def _build_card_list(self) -> None:
        self._card_scroll = QScrollArea()
        self._card_scroll.setWidgetResizable(True)
        self._card_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._card_container = QWidget()
        self._card_container.setStyleSheet("background: transparent;")
        self._card_layout = QVBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        self._card_layout.setSpacing(8)
        self._card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._card_scroll.setWidget(self._card_container)
        self._main_layout.addWidget(self._card_scroll, 1)

    def _build_pagination(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)

        self._prev_btn = QPushButton("Previous")
        self._prev_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 8px 16px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #3a3a5e; }}
            QPushButton:disabled {{ color: #555577; }}
        """)
        self._prev_btn.clicked.connect(self._go_prev)
        row.addWidget(self._prev_btn)

        self._page_label = QLabel("Page 1")
        self._page_label.setStyleSheet(f"font-size: 13px; color: {TEXT_MUTED}; background: transparent;")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._page_label)

        self._next_btn = QPushButton("Next")
        self._next_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 8px 16px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #3a3a5e; }}
            QPushButton:disabled {{ color: #555577; }}
        """)
        self._next_btn.clicked.connect(self._go_next)
        row.addWidget(self._next_btn)

        self._main_layout.addLayout(row)

    def _go_prev(self) -> None:
        if self._page > 1:
            self._page -= 1
            self._load_data()

    def _go_next(self) -> None:
        self._page += 1
        self._load_data()

    def _load_data(self) -> None:
        try:
            if not self.isWidgetType() and not self.isWindow():
                return
        except RuntimeError:
            return
        try:
            params = {
                "user_id": get_active_user_id(),
                "page": self._page,
                "page_size": self._page_size,
            }
            resp = httpx.get(f"{API_BASE}/bookmarks?{urlencode(params)}", timeout=10)
            resp.raise_for_status()
            self._data = resp.json()
            self._render()
        except Exception as exc:
            self._render_offline(str(exc))

    def _render(self) -> None:
        self._clear_card_layout()
        items = self._data.get("items", [])
        total = self._data.get("total", 0)

        self._result_count_label.setText(f"{total} total")
        self._page_label.setText(f"Page {self._data.get('page', 1)}")
        self._prev_btn.setEnabled(self._page > 1)
        self._next_btn.setEnabled(self._page * self._page_size < total)

        if not items:
            lbl = QLabel("No bookmarks yet. Browse opportunities and bookmark the ones you like.")
            lbl.setStyleSheet(f"font-size: 14px; color: {TEXT_MUTED}; background: transparent; padding: 40px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._card_layout.addWidget(lbl)
            return

        for bm_data in items:
            row = BookmarkRow(bm_data, on_remove=self._on_row_removed)
            self._card_layout.addWidget(row)

    def _render_offline(self, msg: str) -> None:
        self._clear_card_layout()
        self._result_count_label.setText("Offline")
        lbl = QLabel("API not available — start the server")
        lbl.setStyleSheet(f"font-size: 14px; color: {TEXT_MUTED}; background: transparent; padding: 40px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._card_layout.addWidget(lbl)

    def _clear_card_layout(self) -> None:
        while self._card_layout.count():
            item = self._card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_row_removed(self, bm_id: str) -> None:
        self._load_data()
