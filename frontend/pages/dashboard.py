"""Dashboard page with stats, graphs, and data tables."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.request import urlopen

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QPieSeries,
    QValueAxis,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from frontend.pages.base import PageWidget

ACCENT = "#7c3aed"
ACCENT_LIGHT = "#a78bfa"
BG_CARD = "#1a1a2e"
TEXT_MUTED = "#8888bb"
TEXT_BRIGHT = "#f0f0ff"
CARD_RADIUS = "8px"

PALETTE = ["#7c3aed", "#2563eb", "#10b981", "#f59e0b", "#ef4444", "#ec4899", "#06b6d4", "#84cc16"]


class DashCard(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dashCard")
        self.setStyleSheet(f"""
            QFrame#dashCard {{
                background-color: {BG_CARD};
                border-radius: {CARD_RADIUS};
                padding: 16px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header = QLabel(title)
        header.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {TEXT_MUTED}; background: transparent;")
        layout.addWidget(header)

        self._body = QWidget()
        self._body.setStyleSheet("background: transparent;")
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._body, 1)

    def body(self) -> QVBoxLayout:
        return self._body_layout

    def clear_body(self) -> None:
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class StatCard(QFrame):
    def __init__(self, label: str, value: str, color: str = ACCENT, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setStyleSheet(f"""
            QFrame#statCard {{
                background-color: {BG_CARD};
                border-radius: {CARD_RADIUS};
                border-left: 3px solid {color};
                padding: 12px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        val = QLabel(value)
        val.setStyleSheet(f"font-size: 28px; font-weight: 700; color: {TEXT_BRIGHT}; background: transparent;")
        layout.addWidget(val)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED}; background: transparent;")
        layout.addWidget(lbl)


def _make_table(headers: list[str], rows: list[list[str]], max_rows: int = 10) -> QTableWidget:
    table = QTableWidget(min(len(rows), max_rows), len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    table.setShowGrid(False)
    table.setStyleSheet(f"""
        QTableWidget {{
            background-color: transparent;
            border: none;
            font-size: 12px;
            color: {TEXT_BRIGHT};
        }}
        QTableWidget::item {{
            padding: 6px 4px;
            border-bottom: 1px solid #2a2a44;
        }}
        QHeaderView::section {{
            background-color: transparent;
            color: {TEXT_MUTED};
            font-weight: 600;
            font-size: 11px;
            padding: 6px 4px;
            border: none;
            border-bottom: 1px solid #3a3a5e;
        }}
    """)

    for r, row in enumerate(rows[:max_rows]):
        for c, val in enumerate(row):
            item = QTableWidgetItem(str(val))
            item.setForeground(QColor(TEXT_BRIGHT))
            table.setItem(r, c, item)

    return table


def _make_chart_view(chart: QChart) -> QChartView:
    view = QChartView(chart)
    view.setRenderHint(view.renderHint())
    view.setStyleSheet("background: transparent; border: none;")
    chart.setBackgroundBrush(QColor(BG_CARD))
    chart.setMargins(0, 0, 0, 0)
    chart.legend().setLabelColor(QColor(TEXT_MUTED))
    return view


class DashboardPage(PageWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        self._data: dict[str, Any] = {}
        super().__init__("Dashboard", parent)

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
        self._main_layout.setSpacing(20)

        self._build_header()
        self._build_stats_row()
        self._build_top_opps()
        self._build_graphs_row()
        self._build_recent_searches()
        self._build_deadlines()
        self._build_bookmarks()
        self._main_layout.addStretch()

        QTimer.singleShot(0, self._load_data)

    def _build_header(self) -> None:
        header = QLabel("Dashboard")
        header.setStyleSheet(f"font-size: 24px; font-weight: 600; color: {TEXT_BRIGHT}; background: transparent;")
        self._main_layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("QFrame { color: #2a2a44; max-height: 1px; }")
        self._main_layout.addWidget(sep)

    def _build_stats_row(self) -> None:
        self._stats_widget = QWidget()
        self._stats_widget.setStyleSheet("background: transparent;")
        self._stats_layout = QHBoxLayout(self._stats_widget)
        self._stats_layout.setSpacing(16)
        self._stats_layout.setContentsMargins(0, 0, 0, 0)

        self._stat_labels = [
            ("total_opportunities", "Opportunities", ACCENT),
            ("today_searches", "Today's Searches", "#2563eb"),
            ("total_bookmarks", "Bookmarks", "#10b981"),
            ("unread_notifications", "Notifications", "#f59e0b"),
            ("avg_relevance_score", "Avg Score", "#ec4899"),
        ]
        self._stat_cards: list[StatCard] = []

        for key, label, color in self._stat_labels:
            card = StatCard(label, "—", color)
            self._stat_cards.append(card)
            self._stats_layout.addWidget(card)

        self._main_layout.addWidget(self._stats_widget)

    def _build_top_opps(self) -> None:
        card = DashCard("Top Opportunities")
        self._top_opps_layout = card.body()
        self._main_layout.addWidget(card)

    def _build_graphs_row(self) -> None:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setSpacing(16)
        row_layout.setContentsMargins(0, 0, 0, 0)

        score_card = DashCard("Score Distribution")
        self._score_chart_layout = score_card.body()
        row_layout.addWidget(score_card, 1)

        status_card = DashCard("Status Breakdown")
        self._status_chart_layout = status_card.body()
        row_layout.addWidget(status_card, 1)

        trend_card = DashCard("14-Day Trend")
        self._trend_chart_layout = trend_card.body()
        row_layout.addWidget(trend_card, 1)

        self._main_layout.addWidget(row)

    def _build_recent_searches(self) -> None:
        card = DashCard("Recent Searches")
        self._searches_layout = card.body()
        self._main_layout.addWidget(card)

    def _build_deadlines(self) -> None:
        card = DashCard("Upcoming Deadlines")
        self._deadlines_layout = card.body()
        self._main_layout.addWidget(card)

    def _build_bookmarks(self) -> None:
        card = DashCard("Bookmarks")
        self._bookmarks_layout = card.body()
        self._main_layout.addWidget(card)

    def _load_data(self) -> None:
        try:
            if not self.isWidgetType() and not self.isWindow():
                return
        except RuntimeError:
            return
        try:
            import urllib.request
            resp = urllib.request.urlopen(
                "http://127.0.0.1:8000/api/v1/dashboard?user_id=00000000-0000-0000-0000-000000000000",
                timeout=5,
            )
            self._data = json.loads(resp.read().decode())
            self._render()
        except Exception as e:
            self._render_offline(str(e))

    def _render(self) -> None:
        data = self._data
        stats = data.get("stats", {})

        for card, (key, _, _) in zip(self._stat_cards, self._stat_labels):
            val = stats.get(key, "—")
            if isinstance(val, float):
                val = f"{val:.1f}"
            card.findChildren(QLabel)[0].setText(str(val))

        self._render_top_opps(data.get("top_opportunities", []))
        self._render_score_chart(data.get("score_distribution", []))
        self._render_status_chart(data.get("status_breakdown", []))
        self._render_trend_chart(data.get("daily_trend", []))
        self._render_searches(data.get("recent_searches", []))
        self._render_deadlines(data.get("upcoming_deadlines", []))
        self._render_bookmarks(data.get("bookmarks", []))

    def _render_offline(self, msg: str) -> None:
        for card in self._stat_cards:
            card.findChildren(QLabel)[0].setText("—")
        for layout_name in ("_top_opps_layout", "_searches_layout", "_deadlines_layout", "_bookmarks_layout"):
            layout = getattr(self, layout_name, None)
            if layout:
                layout.addWidget(QLabel("API not available — start the server"))
        for layout_name in ("_score_chart_layout", "_status_chart_layout", "_trend_chart_layout"):
            layout = getattr(self, layout_name, None)
            if layout:
                layout.addWidget(QLabel("Charts unavailable offline"))

    def _render_top_opps(self, opps: list[dict]) -> None:
        self._clear_layout(self._top_opps_layout)
        if not opps:
            self._top_opps_layout.addWidget(QLabel("No scored opportunities yet"))
            return
        headers = ["Title", "Score", "Status", "Priority", "Deadline"]
        rows = [
            [
                o.get("title", "")[:60],
                str(o.get("relevance_score", "") or "—"),
                o.get("status", ""),
                o.get("priority", ""),
                o.get("application_deadline", "") or "—",
            ]
            for o in opps
        ]
        self._top_opps_layout.addWidget(_make_table(headers, rows))

    def _render_score_chart(self, dist: list[dict]) -> None:
        self._clear_layout(self._score_chart_layout)
        if not dist:
            self._score_chart_layout.addWidget(QLabel("No score data"))
            return

        series = QBarSet("Opportunities")
        series.setColor(QColor(ACCENT))
        categories: list[str] = []
        for d in dist:
            series.append(d.get("count", 0))
            categories.append(f"{d.get('range_start', 0)}-{d.get('range_end', 100)}")

        bar_series = QBarSeries()
        bar_series.append(series)

        chart = QChart()
        chart.addSeries(bar_series)
        chart.setTitle("Score Distribution")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsColor(QColor(TEXT_MUTED))
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        bar_series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setLabelsColor(QColor(TEXT_MUTED))
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_y)

        self._score_chart_layout.addWidget(_make_chart_view(chart))

    def _render_status_chart(self, breakdown: list[dict]) -> None:
        self._clear_layout(self._status_chart_layout)
        if not breakdown:
            self._status_chart_layout.addWidget(QLabel("No status data"))
            return

        series = QPieSeries()
        for i, d in enumerate(breakdown):
            label = f"{d.get('status', 'unknown')} ({d.get('count', 0)})"
            sl = series.append(label, d.get("count", 0))
            sl.setColor(QColor(PALETTE[i % len(PALETTE)]))

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("Status Breakdown")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        self._status_chart_layout.addWidget(_make_chart_view(chart))

    def _render_trend_chart(self, trend: list[dict]) -> None:
        self._clear_layout(self._trend_chart_layout)
        if not trend:
            self._trend_chart_layout.addWidget(QLabel("No trend data"))
            return

        series = QBarSet("Discovered")
        series.setColor(QColor("#2563eb"))
        categories: list[str] = []
        for d in trend:
            series.append(d.get("count", 0))
            date_str = d.get("date", "")
            categories.append(date_str[-5:] if date_str else "")

        bar_series = QBarSeries()
        bar_series.append(series)

        chart = QChart()
        chart.addSeries(bar_series)
        chart.setTitle("14-Day Trend")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsColor(QColor(TEXT_MUTED))
        axis_x.setLabelsAngle(-45)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        bar_series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setLabelsColor(QColor(TEXT_MUTED))
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_y)

        self._trend_chart_layout.addWidget(_make_chart_view(chart))

    def _render_searches(self, searches: list[dict]) -> None:
        self._clear_layout(self._searches_layout)
        if not searches:
            self._searches_layout.addWidget(QLabel("No searches yet"))
            return
        headers = ["Query", "Results", "Last Run"]
        rows = [
            [
                s.get("query", "")[:60],
                str(s.get("result_count", 0)),
                s.get("last_run_at", "") or s.get("created_at", "") or "—",
            ]
            for s in searches
        ]
        self._searches_layout.addWidget(_make_table(headers, rows))

    def _render_deadlines(self, deadlines: list[dict]) -> None:
        self._clear_layout(self._deadlines_layout)
        if not deadlines:
            self._deadlines_layout.addWidget(QLabel("No upcoming deadlines"))
            return
        headers = ["Title", "Deadline", "Score"]
        rows = [
            [
                d.get("title", "")[:60],
                d.get("application_deadline", "") or "—",
                str(d.get("relevance_score", "") or "—"),
            ]
            for d in deadlines
        ]
        self._deadlines_layout.addWidget(_make_table(headers, rows))

    def _render_bookmarks(self, bookmarks: list[dict]) -> None:
        self._clear_layout(self._bookmarks_layout)
        if not bookmarks:
            self._bookmarks_layout.addWidget(QLabel("No bookmarks yet"))
            return
        headers = ["Title", "Notes", "Added"]
        rows = [
            [
                b.get("opportunity_title", "")[:60],
                (b.get("notes", "") or "")[:40],
                b.get("created_at", "")[:10] if b.get("created_at") else "—",
            ]
            for b in bookmarks
        ]
        self._bookmarks_layout.addWidget(_make_table(headers, rows))

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
