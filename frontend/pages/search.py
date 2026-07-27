"""Search page — run the search pipeline with configurable options."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from frontend.pages.base import PageWidget
from frontend.user_context import get_active_user_id

ACCENT = "#7c3aed"
ACCENT_LIGHT = "#a78bfa"
BG_CARD = "#1a1a2e"
TEXT_MUTED = "#8888bb"
TEXT_BRIGHT = "#f0f0ff"
GREEN = "#10b981"
AMBER = "#f59e0b"
RED = "#ef4444"

API_BASE = "http://127.0.0.1:8000/api/v1"


ALL_PROFILES_TOKEN = "__all__"


class PipelineWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__()
        self._params = params

    def run(self) -> None:
        try:
            resp = httpx.post(f"{API_BASE}/pipeline/run", params=self._params, timeout=300)
            if resp.status_code == 200:
                self.finished.emit(resp.json())
            else:
                try:
                    data = resp.json()
                    msg = data.get("error", f"HTTP {resp.status_code}")
                except Exception:
                    msg = f"HTTP {resp.status_code}"
                self.error.emit(msg)
        except Exception as exc:
            self.error.emit(str(exc))


class MultiPipelineWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, base_params: dict[str, Any], profile_ids: list[str]) -> None:
        super().__init__()
        self._base_params = base_params
        self._profile_ids = profile_ids

    def run(self) -> None:
        aggregated: dict[str, Any] = {
            "success": True,
            "multi_pipeline": True,
            "pipelines_run": len(self._profile_ids),
            "queries_generated": [],
            "search_results_count": 0,
            "pages_extracted": 0,
            "opportunities_created": 0,
            "opportunities_skipped_duplicate": 0,
            "opportunities_scored": 0,
            "notifications_sent": 0,
            "per_profile": [],
            "errors": [],
        }
        for pid in self._profile_ids:
            params = {**self._base_params, "profile_id": pid}
            try:
                resp = httpx.post(f"{API_BASE}/pipeline/run", params=params, timeout=300)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        aggregated["queries_generated"].extend(data.get("queries_generated", []))
                        aggregated["search_results_count"] += data.get("search_results_count", 0)
                        aggregated["pages_extracted"] += data.get("pages_extracted", 0)
                        aggregated["opportunities_created"] += data.get("opportunities_created", 0)
                        aggregated["opportunities_skipped_duplicate"] += data.get("opportunities_skipped_duplicate", 0)
                        aggregated["opportunities_scored"] += data.get("opportunities_scored", 0)
                        aggregated["notifications_sent"] += data.get("notifications_sent", 0)
                        aggregated["per_profile"].append({"profile_id": pid, "status": "ok"})
                    else:
                        aggregated["errors"].append({"profile_id": pid, "error": data.get("error", "unknown")})
                        aggregated["per_profile"].append({"profile_id": pid, "status": "error"})
                else:
                    aggregated["errors"].append({"profile_id": pid, "error": f"HTTP {resp.status_code}"})
                    aggregated["per_profile"].append({"profile_id": pid, "status": "error"})
            except Exception as exc:
                aggregated["errors"].append({"profile_id": pid, "error": str(exc)})
                aggregated["per_profile"].append({"profile_id": pid, "status": "error"})

        if aggregated["errors"] and aggregated["search_results_count"] == 0:
            aggregated["success"] = False
            aggregated["error"] = f"{len(aggregated['errors'])} of {len(self._profile_ids)} pipelines failed"

        self.finished.emit(aggregated)


class SearchPage(PageWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        self._is_running = False
        self._last_result: dict[str, Any] | None = None
        self._provider_names: list[str] = []
        super().__init__("Search", parent)

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
        self._build_options()
        self._build_run_button()
        self._build_progress()
        self._build_results_panel()
        self._build_last_run()
        self._main_layout.addStretch()

        QTimer.singleShot(0, self._load_providers)

    def _build_header(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)

        title = QLabel("Search")
        title.setStyleSheet(f"font-size: 24px; font-weight: 600; color: {TEXT_BRIGHT}; background: transparent;")
        row.addWidget(title)

        row.addStretch()

        self._main_layout.addLayout(row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("QFrame { color: #2a2a44; max-height: 1px; }")
        self._main_layout.addWidget(sep)

    def _build_options(self) -> None:
        card = QFrame()
        card.setObjectName("optionsCard")
        card.setStyleSheet(f"""
            QFrame#optionsCard {{
                background-color: {BG_CARD}; border-radius: 8px; padding: 0px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)

        provider_row = QHBoxLayout()
        provider_row.setSpacing(12)
        lbl = QLabel("Search Provider")
        lbl.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {TEXT_BRIGHT}; background: transparent;")
        provider_row.addWidget(lbl)
        provider_row.addStretch()
        self._provider_combo = QComboBox()
        self._provider_combo.setMinimumWidth(200)
        self._provider_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 6px 12px; font-size: 12px;
            }}
            QComboBox:hover {{ background-color: #3a3a5e; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox QAbstractItemView {{
                background-color: #1a1a2e; color: {TEXT_BRIGHT};
                selection-background-color: {ACCENT};
            }}
        """)
        provider_row.addWidget(self._provider_combo)
        card_layout.addLayout(provider_row)

        profile_row = QHBoxLayout()
        profile_row.setSpacing(12)
        plbl = QLabel("Profile")
        plbl.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {TEXT_BRIGHT}; background: transparent;")
        profile_row.addWidget(plbl)
        profile_row.addStretch()
        self._profile_combo = QComboBox()
        self._profile_combo.setMinimumWidth(200)
        self._profile_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 6px 12px; font-size: 12px;
            }}
            QComboBox:hover {{ background-color: #3a3a5e; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox QAbstractItemView {{
                background-color: #1a1a2e; color: {TEXT_BRIGHT};
                selection-background-color: {ACCENT};
            }}
        """)
        profile_row.addWidget(self._profile_combo)
        card_layout.addLayout(profile_row)

        spin_row = QHBoxLayout()
        spin_row.setSpacing(24)

        q_lbl = QLabel("Max Queries")
        q_lbl.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {TEXT_BRIGHT}; background: transparent;")
        spin_row.addWidget(q_lbl)
        self._queries_spin = QSpinBox()
        self._queries_spin.setRange(1, 20)
        self._queries_spin.setValue(5)
        self._queries_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 6px 12px; font-size: 12px;
                min-width: 80px;
            }}
            QSpinBox:hover {{ background-color: #3a3a5e; }}
            QSpinBox::up-button, QSpinBox::down-button {{ border: none; width: 16px; }}
        """)
        spin_row.addWidget(self._queries_spin)

        r_lbl = QLabel("Max Results")
        r_lbl.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {TEXT_BRIGHT}; background: transparent;")
        spin_row.addWidget(r_lbl)
        self._results_spin = QSpinBox()
        self._results_spin.setRange(1, 50)
        self._results_spin.setValue(10)
        self._results_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 6px 12px; font-size: 12px;
                min-width: 80px;
            }}
            QSpinBox:hover {{ background-color: #3a3a5e; }}
            QSpinBox::up-button, QSpinBox::down-button {{ border: none; width: 16px; }}
        """)
        spin_row.addWidget(self._results_spin)

        spin_row.addStretch()
        card_layout.addLayout(spin_row)

        check_row = QHBoxLayout()
        check_row.setSpacing(12)
        self._skip_rank_check = QCheckBox("Skip AI Ranking (faster)")
        self._skip_rank_check.setStyleSheet(f"""
            QCheckBox {{
                font-size: 13px; color: {TEXT_BRIGHT}; background: transparent;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px; height: 18px;
                border: 2px solid #3a3a5e; border-radius: 4px;
                background-color: #2a2a44;
            }}
            QCheckBox::indicator:checked {{
                background-color: {ACCENT}; border-color: {ACCENT};
            }}
        """)
        check_row.addWidget(self._skip_rank_check)
        check_row.addStretch()
        card_layout.addLayout(check_row)

        self._main_layout.addWidget(card)

    def _build_run_button(self) -> None:
        self._run_btn = QPushButton("Run Search Now")
        self._run_btn.setMinimumHeight(48)
        self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT}; color: white; border: none;
                border-radius: 8px; font-size: 15px; font-weight: 700;
            }}
            QPushButton:hover {{ background-color: #6d28d9; }}
            QPushButton:disabled {{ background-color: #3a3a5e; color: #666688; }}
        """)
        self._run_btn.clicked.connect(self._run_pipeline)
        self._main_layout.addWidget(self._run_btn)

    def _build_progress(self) -> None:
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: #2a2a44; border: none; border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT}; border-radius: 3px;
            }}
        """)
        self._progress.hide()
        self._main_layout.addWidget(self._progress)

    def _build_results_panel(self) -> None:
        self._results_card = QFrame()
        self._results_card.setObjectName("resultsCard")
        self._results_card.setStyleSheet(f"""
            QFrame#resultsCard {{
                background-color: {BG_CARD}; border-radius: 8px; padding: 0px;
            }}
        """)
        results_layout = QVBoxLayout(self._results_card)
        results_layout.setContentsMargins(20, 16, 20, 16)
        results_layout.setSpacing(8)

        header_row = QHBoxLayout()
        self._results_icon = QLabel()
        self._results_icon.setStyleSheet("background: transparent;")
        header_row.addWidget(self._results_icon)

        self._results_title = QLabel()
        self._results_title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {TEXT_BRIGHT}; background: transparent;")
        header_row.addWidget(self._results_title)
        header_row.addStretch()
        results_layout.addLayout(header_row)

        self._results_body = QVBoxLayout()
        results_layout.addLayout(self._results_body)

        nav_row = QHBoxLayout()
        nav_row.setSpacing(8)
        nav_row.addStretch()
        self._view_results_btn = QPushButton("View Results")
        self._view_results_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT}; color: white; border: none;
                border-radius: 6px; padding: 8px 16px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #6d28d9; }}
        """)
        self._view_results_btn.clicked.connect(self._navigate_to_opportunities)
        nav_row.addWidget(self._view_results_btn)
        results_layout.addLayout(nav_row)

        self._results_card.hide()
        self._main_layout.addWidget(self._results_card)

    def _build_last_run(self) -> None:
        self._last_run_card = QFrame()
        self._last_run_card.setObjectName("lastRunCard")
        self._last_run_card.setStyleSheet(f"""
            QFrame#lastRunCard {{
                background-color: {BG_CARD}; border-radius: 8px; padding: 0px;
            }}
        """)
        lr_layout = QHBoxLayout(self._last_run_card)
        lr_layout.setContentsMargins(20, 12, 20, 12)
        lr_layout.setSpacing(8)

        lr_label = QLabel("Last Run")
        lr_label.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {TEXT_MUTED}; background: transparent;")
        lr_layout.addWidget(lr_label)

        self._last_run_info = QLabel("No previous runs")
        self._last_run_info.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED}; background: transparent;")
        lr_layout.addWidget(self._last_run_info, 1)

        lr_layout.addStretch()
        self._last_run_card.hide()
        self._main_layout.addWidget(self._last_run_card)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._load_providers()

    def _load_providers(self) -> None:
        try:
            if not self.isWidgetType() and not self.isWindow():
                return
        except RuntimeError:
            return
        try:
            resp = httpx.get(f"{API_BASE}/search-providers", timeout=10)
            resp.raise_for_status()
            all_providers = [p["name"] for p in resp.json()]
            self._provider_names = [name for name in all_providers if name.lower() == "tavily"]
            self._provider_combo.clear()
            for name in self._provider_names:
                self._provider_combo.addItem(name)
        except Exception:
            self._provider_combo.clear()
            self._provider_combo.addItem("tavily")
            self._provider_names = ["tavily"]
        self._load_latest_run()
        self._load_profiles()

    def _load_profiles(self) -> None:
        try:
            if not self.isWidgetType() and not self.isWindow():
                return
        except RuntimeError:
            return
        try:
            resp = httpx.get(
                f"{API_BASE}/users/{get_active_user_id()}/profiles",
                timeout=10,
            )
            resp.raise_for_status()
            profiles = resp.json()
            self._profile_combo.clear()
            if profiles:
                self._profile_combo.addItem(
                    f"All Profiles ({len(profiles)} slots)", ALL_PROFILES_TOKEN,
                )
            for p in profiles:
                label = p.get("name", "Unnamed")
                self._profile_combo.addItem(label, p.get("id"))
        except Exception:
            self._profile_combo.clear()
            self._profile_combo.addItem("No profiles available", None)

    def _load_latest_run(self) -> None:
        try:
            if not self.isWidgetType() and not self.isWindow():
                return
        except RuntimeError:
            return
        try:
            resp = httpx.get(
                f"{API_BASE}/searches/latest?user_id={get_active_user_id()}",
                timeout=10,
            )
            if resp.status_code == 200 and resp.json():
                data = resp.json()
                ts = data.get("created_at", "")
                count = data.get("result_count", 0)
                self._last_run_info.setText(f"Results: {count}  |  {ts[:19]}")
                self._last_run_card.show()
        except Exception:
            pass

    def _run_pipeline(self) -> None:
        self._is_running = True
        self._run_btn.setEnabled(False)
        self._results_card.hide()
        self._progress.show()

        profile_id = self._profile_combo.currentData()
        if not profile_id:
            self._on_error("No profile selected. Create a profile first.")
            return

        base_params = {
            "search_provider": self._provider_combo.currentText().lower(),
            "max_queries": self._queries_spin.value(),
            "max_results": self._results_spin.value(),
            "skip_ranking": self._skip_rank_check.isChecked(),
        }

        if profile_id == ALL_PROFILES_TOKEN:
            profile_ids = [
                self._profile_combo.itemData(i)
                for i in range(self._profile_combo.count())
                if self._profile_combo.itemData(i) and self._profile_combo.itemData(i) != ALL_PROFILES_TOKEN
            ]
            if not profile_ids:
                self._on_error("No individual profiles available.")
                return
            self._thread = QThread()
            self._worker = MultiPipelineWorker(base_params, profile_ids)
            self._worker.moveToThread(self._thread)
            self._thread.started.connect(self._worker.run)
        else:
            base_params["profile_id"] = profile_id
            self._thread = QThread()
            self._worker = PipelineWorker(base_params)
            self._worker.moveToThread(self._thread)
            self._thread.started.connect(self._worker.run)

        self._worker.finished.connect(self._on_success)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)

        self._thread.start()

    def _on_success(self, data: dict[str, Any]) -> None:
        if data.get("success", False):
            self._last_result = data
            self._show_success(data)
            return

        self._last_result = None
        self._show_error(data.get("error", "Search pipeline failed."))

    def _on_error(self, msg: str) -> None:
        self._last_result = None
        self._show_error(msg)

    def _show_success(self, data: dict[str, Any]) -> None:
        is_multi = data.get("multi_pipeline", False)

        self._results_icon.setText("")
        if is_multi:
            self._results_title.setText("Multi-Pipeline Search Complete")
            self._results_title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {GREEN}; background: transparent;")
        else:
            self._results_title.setText("Search Complete")
            self._results_title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {GREEN}; background: transparent;")

        self._clear_body()

        if is_multi:
            fields = [
                ("Pipelines Run", str(data.get("pipelines_run", 0))),
                ("Total Search Results", str(data.get("search_results_count", 0))),
                ("Total Pages Extracted", str(data.get("pages_extracted", 0))),
                ("Total Opportunities Created", str(data.get("opportunities_created", 0))),
                ("Duplicates Skipped", str(data.get("opportunities_skipped_duplicate", 0))),
                ("Opportunities Scored", str(data.get("opportunities_scored", 0))),
                ("Notifications Sent", str(data.get("notifications_sent", 0))),
            ]
            per_profile = data.get("per_profile", [])
            if per_profile:
                ok_count = sum(1 for p in per_profile if p["status"] == "ok")
                err_count = sum(1 for p in per_profile if p["status"] == "error")
                fields.append(("Profiles Succeeded", str(ok_count)))
                fields.append(("Profiles Failed", str(err_count)))
        else:
            fields = [
                ("Queries Generated", ", ".join(data.get("queries_generated", [])) or "None"),
                ("Search Results Found", str(data.get("search_results_count", 0))),
                ("Pages Extracted", str(data.get("pages_extracted", 0))),
                ("Opportunities Created", str(data.get("opportunities_created", 0))),
                ("Opportunities Skipped (Duplicates)", str(data.get("opportunities_skipped_duplicate", 0))),
                ("Opportunities Scored", str(data.get("opportunities_scored", 0))),
                ("Notifications Sent", str(data.get("notifications_sent", 0))),
            ]

        for label, value in fields:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet(f"font-size: 12px; font-weight: 500; color: {TEXT_MUTED}; background: transparent;")
            row.addWidget(lbl)
            val = QLabel(value)
            val.setStyleSheet(f"font-size: 12px; color: {TEXT_BRIGHT}; background: transparent;")
            row.addWidget(val)
            row.addStretch()
            self._results_body.addLayout(row)

        self._view_results_btn.show()
        self._results_card.show()

    def _show_error(self, msg: str) -> None:
        self._results_icon.setText("")
        self._results_title.setText("Search Failed")
        self._results_title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {RED}; background: transparent;")

        self._clear_body()
        err = QLabel(msg)
        err.setWordWrap(True)
        err.setStyleSheet(f"font-size: 12px; color: {RED}; background: transparent;")
        self._results_body.addWidget(err)

        self._view_results_btn.hide()
        self._results_card.show()

    def _clear_body(self) -> None:
        while self._results_body.count():
            item = self._results_body.takeAt(0)
            if item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
            elif item.widget():
                item.widget().deleteLater()

    def _cleanup_thread(self) -> None:
        if self._worker:
            self._worker.deleteLater()
        self._progress.hide()
        self._run_btn.setEnabled(True)
        self._is_running = False
        self._load_latest_run()

    def _navigate_to_opportunities(self) -> None:
        window = self.window()
        if hasattr(window, "_navigate"):
            window._navigate(3)
