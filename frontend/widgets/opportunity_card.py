"""Shared opportunity card widget — used by Opportunities and Bookmarks pages."""

from __future__ import annotations

from typing import Any

import httpx
from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

ACCENT = "#7c3aed"
ACCENT_LIGHT = "#a78bfa"
BG_CARD = "#1a1a2e"
TEXT_MUTED = "#8888bb"
TEXT_BRIGHT = "#f0f0ff"
CARD_RADIUS = "8px"
GREEN = "#10b981"
AMBER = "#f59e0b"
RED = "#ef4444"

USER_ID = "00000000-0000-0000-0000-000000000000"
API_BASE = "http://127.0.0.1:8000/api/v1"


class OpportunityCard(QFrame):
    """A rich card displaying one opportunity with score, strengths, gaps, and actions."""

    def __init__(self, data: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data = data
        self._opp_id = data.get("id", "")
        self.setObjectName("oppCard")
        score = data.get("relevance_score")
        score_color = GREEN if score and score >= 70 else (AMBER if score and score >= 40 else RED)
        self.setStyleSheet(f"""
            QFrame#oppCard {{
                background-color: {BG_CARD};
                border-radius: {CARD_RADIUS};
                border-left: 3px solid {score_color};
                padding: 12px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        self._build_header_row(layout, score, score_color)
        self._build_summary(layout)
        self._build_details(layout)
        self._build_actions(layout)

    def _build_header_row(self, layout: QVBoxLayout, score: float | None, score_color: str) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)

        title = self._data.get("title", "Untitled")
        url = self._data.get("url", "")
        title_label = QLabel(title[:80])
        title_label.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_BRIGHT}; background: transparent;")
        if url:
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

        status = self._data.get("status", "new")
        status_label = QLabel(status.capitalize())
        status_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px; font-weight: 600; color: {ACCENT};
                background: #2a1a4e; border-radius: 4px; padding: 2px 10px;
            }}
        """)
        row.addWidget(status_label)

        layout.addLayout(row)

    def _build_summary(self, layout: QVBoxLayout) -> None:
        summary = self._data.get("summary") or self._data.get("description") or ""
        if summary:
            s = QLabel(summary[:300])
            s.setWordWrap(True)
            s.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED}; background: transparent; padding: 2px 0;")
            layout.addWidget(s)

        deadline = self._data.get("application_deadline")
        if deadline:
            dl = QLabel(f"Deadline: {deadline}")
            dl.setStyleSheet(f"font-size: 11px; color: {AMBER}; font-weight: 600; background: transparent;")
            layout.addWidget(dl)

    def _build_details(self, layout: QVBoxLayout) -> None:
        pros = self._data.get("pros") or []
        cons = self._data.get("cons") or []
        missing = self._data.get("missing_skills") or []
        explanation = self._data.get("ranking_explanation")

        if pros:
            label = QLabel("Strengths")
            label.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {GREEN}; background: transparent; margin-top: 4px;")
            layout.addWidget(label)
            for p in pros:
                pl = QLabel(f"  + {p}")
                pl.setWordWrap(True)
                pl.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;")
                layout.addWidget(pl)

        if missing:
            label = QLabel("Gaps — Missing Skills")
            label.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {RED}; background: transparent; margin-top: 4px;")
            layout.addWidget(label)
            for m in missing:
                ml = QLabel(f"  - {m}")
                ml.setWordWrap(True)
                ml.setStyleSheet(f"font-size: 11px; color: {RED}99; background: transparent;")
                layout.addWidget(ml)

        if cons:
            label = QLabel("Gaps — Concerns")
            label.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {AMBER}; background: transparent; margin-top: 4px;")
            layout.addWidget(label)
            for c in cons:
                cl = QLabel(f"  - {c}")
                cl.setWordWrap(True)
                cl.setStyleSheet(f"font-size: 11px; color: {AMBER}99; background: transparent;")
                layout.addWidget(cl)

        if explanation:
            ex = QLabel(f"Ranking: {explanation[:200]}")
            ex.setWordWrap(True)
            ex.setStyleSheet(f"font-size: 11px; color: {ACCENT_LIGHT}; font-style: italic; background: transparent; margin-top: 2px;")
            layout.addWidget(ex)

    def _build_actions(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)

        bookmark_btn = QPushButton("Bookmark")
        bookmark_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #3a3a5e; }}
        """)
        bookmark_btn.clicked.connect(self._bookmark)
        row.addWidget(bookmark_btn)

        status_combo = QComboBox()
        status_combo.addItems(["new", "reviewed", "applied", "interview", "rejected", "accepted"])
        current_status = self._data.get("status", "new")
        idx = status_combo.findText(current_status)
        if idx >= 0:
            status_combo.setCurrentIndex(idx)
        status_combo.currentTextChanged.connect(self._change_status)
        status_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: 600;
            }}
            QComboBox:hover {{ background-color: #3a3a5e; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox QAbstractItemView {{
                background-color: #1a1a2e; color: {TEXT_BRIGHT};
                selection-background-color: {ACCENT};
            }}
        """)
        row.addWidget(status_combo)

        row.addStretch()
        layout.addLayout(row)

    def _bookmark(self) -> None:
        try:
            httpx.post(
                f"{API_BASE}/bookmarks",
                json={"user_id": USER_ID, "opportunity_id": self._opp_id, "notes": ""},
                timeout=10,
            )
        except Exception:
            pass

    def _change_status(self, new_status: str) -> None:
        try:
            httpx.patch(
                f"{API_BASE}/opportunities/{self._opp_id}/status",
                json={"status": new_status},
                timeout=10,
            )
        except Exception:
            pass
