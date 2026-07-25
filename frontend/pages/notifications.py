"""Notifications page with full UI."""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from frontend.pages.base import PageWidget
from frontend.user_context import get_active_user_id

ACCENT = "#7c3aed"
BG_CARD = "#1a1a2e"
TEXT_MUTED = "#8888bb"
TEXT_BRIGHT = "#f0f0ff"
CARD_RADIUS = "8px"

API_BASE = "http://127.0.0.1:8000/api/v1"


class NotifCard(QFrame):
    def __init__(self, notif_data: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data = notif_data
        self._nid = notif_data.get("id", "")
        self.setObjectName("notifCard")
        is_read = notif_data.get("is_read", False)
        border_color = TEXT_MUTED if is_read else ACCENT
        bg = BG_CARD
        self.setStyleSheet(f"""
            QFrame#notifCard {{
                background-color: {bg};
                border-radius: {CARD_RADIUS};
                border-left: 3px solid {border_color};
                padding: 12px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(12)

        type_label = QLabel(notif_data.get("type", "info"))
        type_label.setStyleSheet(f"""
            QLabel {{
                font-size: 10px; font-weight: 700; color: {ACCENT};
                background: #2a1a4e; border-radius: 4px; padding: 2px 8px;
            }}
        """)
        row.addWidget(type_label)

        title = QLabel(notif_data.get("title", ""))
        title.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {TEXT_BRIGHT}; background: transparent;")
        row.addWidget(title, 1)

        if not is_read:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {ACCENT}; font-size: 10px; background: transparent;")
            row.addWidget(dot)

        ts_str = notif_data.get("created_at", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            ts_display = ts.strftime("%b %d, %H:%M")
        except Exception:
            ts_display = ts_str[:16] if ts_str else ""
        ts_label = QLabel(ts_display)
        ts_label.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;")
        row.addWidget(ts_label)

        layout.addLayout(row)

        msg = notif_data.get("message", "")
        if msg:
            msg_label = QLabel(msg[:200])
            msg_label.setWordWrap(True)
            msg_label.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED}; background: transparent; padding-left: 4px;")
            layout.addWidget(msg_label)

    @property
    def notification_id(self) -> str:
        return self._nid


class NotificationsPage(PageWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        self._data: dict[str, Any] = {}
        super().__init__("Notifications", parent)

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

        self._build_header_row()
        self._build_notifications_area()
        self._main_layout.addStretch()

        QTimer.singleShot(0, self._load_data)

    def _build_header_row(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)

        title = QLabel("Notifications")
        title.setStyleSheet(f"font-size: 24px; font-weight: 600; color: {TEXT_BRIGHT}; background: transparent;")
        row.addWidget(title)

        row.addStretch()

        self._unread_label = QLabel("")
        self._unread_label.setStyleSheet(f"font-size: 13px; color: {TEXT_MUTED}; background: transparent;")
        row.addWidget(self._unread_label)

        mark_btn = QPushButton("Mark All Read")
        mark_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT}; color: white; border: none;
                border-radius: 6px; padding: 8px 16px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #6d28d9; }}
        """)
        mark_btn.clicked.connect(self._mark_all_read)
        row.addWidget(mark_btn)

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

    def _build_notifications_area(self) -> None:
        self._notif_scroll = QScrollArea()
        self._notif_scroll.setWidgetResizable(True)
        self._notif_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._notif_container = QWidget()
        self._notif_container.setStyleSheet("background: transparent;")
        self._notif_layout = QVBoxLayout(self._notif_container)
        self._notif_layout.setContentsMargins(0, 0, 0, 0)
        self._notif_layout.setSpacing(8)
        self._notif_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._notif_scroll.setWidget(self._notif_container)
        self._main_layout.addWidget(self._notif_scroll, 1)

    def _load_data(self) -> None:
        try:
            if not self.isWidgetType() and not self.isWindow():
                return
        except RuntimeError:
            return
        try:
            params = urlencode({"user_id": get_active_user_id(), "limit": 100})
            resp = urllib.request.urlopen(f"{API_BASE}/notifications?{params}", timeout=5)
            self._data = json.loads(resp.read().decode())
            self._render()
        except Exception as exc:
            self._render_offline(str(exc))

    def _render(self) -> None:
        self._clear_notif_layout()
        items = self._data.get("items", [])
        unread_count = self._data.get("unread_count", 0)

        self._unread_label.setText(f"{unread_count} unread" if unread_count else "All caught up!")
        self._unread_label.setStyleSheet(
            f"font-size: 13px; color: {ACCENT if unread_count else '#10b981'}; background: transparent;"
        )

        if not items:
            lbl = QLabel("No notifications yet")
            lbl.setStyleSheet(f"font-size: 14px; color: {TEXT_MUTED}; background: transparent;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._notif_layout.addWidget(lbl)
            return

        for n in items:
            card = NotifCard(n)
            self._notif_layout.addWidget(card)

    def _render_offline(self, msg: str) -> None:
        self._clear_notif_layout()
        self._unread_label.setText("Offline")
        self._unread_label.setStyleSheet(f"font-size: 13px; color: {TEXT_MUTED}; background: transparent;")
        lbl = QLabel("API not available — start the server")
        lbl.setStyleSheet(f"font-size: 14px; color: {TEXT_MUTED}; background: transparent;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._notif_layout.addWidget(lbl)

    def _mark_all_read(self) -> None:
        try:
            if not self.isWidgetType() and not self.isWindow():
                return
        except RuntimeError:
            return
        try:
            params = urlencode({"user_id": get_active_user_id()})
            req = urllib.request.Request(
                f"{API_BASE}/notifications/mark-all-read?{params}",
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
            self._load_data()
        except Exception as exc:
            self._unread_label.setText(f"Error: {exc}")

    def _clear_notif_layout(self) -> None:
        while self._notif_layout.count():
            item = self._notif_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
