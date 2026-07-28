"""Opportunities page — rich card-based opportunity browser with filtering, sorting, and actions."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from frontend.pages.base import PageWidget
from frontend.theme import (
    ACCENT,
    TEXT_BRIGHT,
    TEXT_SECONDARY,
    page_title_stylesheet,
    scroll_area_stylesheet,
    separator_stylesheet,
    transparent_widget_stylesheet,
)
from frontend.user_context import get_active_user_id
from frontend.widgets.opportunity_card import OpportunityCard

TEXT_MUTED = TEXT_SECONDARY

API_BASE = "http://127.0.0.1:8000/api/v1"

STATUS_VALUES = ["", "new", "reviewed", "applied", "interview", "rejected", "accepted"]
STATUS_LABELS = ["All Statuses", "New", "Reviewed", "Applied", "Interview", "Rejected", "Accepted"]


class OpportunitiesPage(PageWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        self._data: dict[str, Any] = {}
        self._page = 1
        self._page_size = 10
        self._status_filter = ""
        self._min_score = 0
        self._sort_by = "score"
        self._profile_id_filter: str | None = None
        super().__init__("Opportunities", parent)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scroll_area_stylesheet())
        layout.addWidget(scroll)

        container = QWidget()
        container.setStyleSheet(transparent_widget_stylesheet())
        scroll.setWidget(container)

        self._main_layout = QVBoxLayout(container)
        self._main_layout.setContentsMargins(36, 36, 36, 36)
        self._main_layout.setSpacing(16)

        self._build_header()
        self._build_filter_bar()
        self._build_card_list()
        self._build_pagination()
        self._main_layout.addStretch()

        self._load_data()
        self._load_profiles()

    def _load_profiles(self) -> None:
        try:
            resp = httpx.get(
                f"{API_BASE}/users/{get_active_user_id()}/profiles",
                timeout=10,
            )
            resp.raise_for_status()
            profiles = resp.json()
            for p in profiles:
                label = p.get("name", "Unnamed")
                self._profile_combo.addItem(label, p.get("id"))
        except Exception:
            pass

    def _build_header(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)

        title = QLabel("Opportunities")
        title.setStyleSheet(page_title_stylesheet())
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
        sep.setStyleSheet(separator_stylesheet())
        self._main_layout.addWidget(sep)

    def _build_filter_bar(self) -> None:
        bar = QHBoxLayout()
        bar.setSpacing(12)

        profile_lbl = QLabel("Profile:")
        profile_lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED}; background: transparent;")
        bar.addWidget(profile_lbl)

        self._profile_combo = QComboBox()
        self._profile_combo.addItem("All Profiles", None)
        self._profile_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 6px 12px; font-size: 12px;
                min-width: 120px;
            }}
            QComboBox:hover {{ background-color: #3a3a5e; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox QAbstractItemView {{
                background-color: #1a1a2e; color: {TEXT_BRIGHT};
                selection-background-color: {ACCENT};
            }}
        """)
        self._profile_combo.currentIndexChanged.connect(self._on_filter_change)
        bar.addWidget(self._profile_combo)

        status_lbl = QLabel("Status:")
        status_lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED}; background: transparent;")
        bar.addWidget(status_lbl)

        self._status_combo = QComboBox()
        self._status_combo.addItems(STATUS_LABELS)
        self._status_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 6px 12px; font-size: 12px;
                min-width: 120px;
            }}
            QComboBox:hover {{ background-color: #3a3a5e; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox QAbstractItemView {{
                background-color: #1a1a2e; color: {TEXT_BRIGHT};
                selection-background-color: {ACCENT};
            }}
        """)
        self._status_combo.currentIndexChanged.connect(self._on_filter_change)
        bar.addWidget(self._status_combo)

        score_lbl = QLabel("Min Score:")
        score_lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED}; background: transparent;")
        bar.addWidget(score_lbl)

        self._score_spin = QSpinBox()
        self._score_spin.setRange(0, 100)
        self._score_spin.setValue(0)
        self._score_spin.setSuffix("%")
        self._score_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 6px 12px; font-size: 12px;
                min-width: 80px;
            }}
            QSpinBox:hover {{ background-color: #3a3a5e; }}
            QSpinBox::up-button, QSpinBox::down-button {{
                border: none; width: 16px;
            }}
        """)
        self._score_spin.valueChanged.connect(self._on_filter_change)
        bar.addWidget(self._score_spin)

        sort_lbl = QLabel("Sort:")
        sort_lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED}; background: transparent;")
        bar.addWidget(sort_lbl)

        self._sort_combo = QComboBox()
        self._sort_combo.addItems(["Score", "Date"])
        self._sort_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 6px 12px; font-size: 12px;
                min-width: 90px;
            }}
            QComboBox:hover {{ background-color: #3a3a5e; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox QAbstractItemView {{
                background-color: #1a1a2e; color: {TEXT_BRIGHT};
                selection-background-color: {ACCENT};
            }}
        """)
        self._sort_combo.currentIndexChanged.connect(self._on_filter_change)
        bar.addWidget(self._sort_combo)

        bar.addStretch()
        self._main_layout.addLayout(bar)

    def _build_card_list(self) -> None:
        self._card_scroll = QScrollArea()
        self._card_scroll.setWidgetResizable(True)
        self._card_scroll.setStyleSheet(scroll_area_stylesheet())

        self._card_container = QWidget()
        self._card_container.setStyleSheet(transparent_widget_stylesheet())
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

    def _on_filter_change(self) -> None:
        self._page = 1
        self._load_data()

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
            idx = self._status_combo.currentIndex()
            status_val = STATUS_VALUES[idx] if 0 <= idx < len(STATUS_VALUES) else ""

            profile_id = self._profile_combo.currentData()
            params = {
                "user_id": get_active_user_id(),
                "page": self._page,
                "page_size": self._page_size,
                "sort_by": "score" if self._sort_combo.currentIndex() == 0 else "date",
                "min_score": self._score_spin.value(),
            }
            if profile_id:
                params["profile_id"] = profile_id
            if status_val:
                params["status"] = status_val

            resp = httpx.get(f"{API_BASE}/opportunities?{urlencode(params)}", timeout=10)
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
            lbl = QLabel("No opportunities yet. Run a search to get started.")
            lbl.setStyleSheet(f"font-size: 14px; color: {TEXT_MUTED}; background: transparent; padding: 40px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._card_layout.addWidget(lbl)
            return

        for opp_data in items:
            card = OpportunityCard(opp_data)
            self._card_layout.addWidget(card)

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
