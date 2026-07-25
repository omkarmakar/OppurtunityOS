"""Settings page — integration status, user preferences, and digest config."""

from __future__ import annotations

from typing import Any

import httpx
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
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

ACCENT = "#7c3aed"
ACCENT_LIGHT = "#a78bfa"
BG_CARD = "#1a1a2e"
TEXT_MUTED = "#8888bb"
TEXT_BRIGHT = "#f0f0ff"
GREEN = "#10b981"
RED = "#ef4444"

USER_ID = "00000000-0000-0000-0000-000000000000"
API_BASE = "http://127.0.0.1:8000/api/v1"


class SettingsSection(QFrame):
    """A labelled settings section card."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sectionCard")
        self.setStyleSheet(f"""
            QFrame#sectionCard {{
                background-color: {BG_CARD}; border-radius: 8px; padding: 0px;
            }}
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 16, 20, 16)
        self._layout.setSpacing(10)

        heading = QLabel(title)
        heading.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {TEXT_BRIGHT}; background: transparent;")
        self._layout.addWidget(heading)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("QFrame { color: #2a2a44; max-height: 1px; }")
        self._layout.addWidget(sep)

    def body(self) -> QVBoxLayout:
        return self._layout


class SettingsPage(PageWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        self._user_settings: dict[str, Any] | None = None
        self._system_settings: dict[str, Any] | None = None
        super().__init__("Settings", parent)

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

        self._build_integrations_section()
        self._build_preferences_section()
        self._build_digest_section()
        self._main_layout.addStretch()

        QTimer.singleShot(0, self._load_all)

    def _build_integrations_section(self) -> None:
        section = SettingsSection("Integrations")
        self._integration_container = QVBoxLayout()
        section.body().addLayout(self._integration_container)
        self._main_layout.addWidget(section)

    def _build_preferences_section(self) -> None:
        section = SettingsSection("Preferences")
        body = section.body()

        theme_row = QHBoxLayout()
        theme_row.setSpacing(12)
        theme_lbl = QLabel("Theme")
        theme_lbl.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {TEXT_BRIGHT}; background: transparent;")
        theme_row.addWidget(theme_lbl)
        theme_row.addStretch()
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["system", "light", "dark"])
        self._theme_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 6px 12px; font-size: 12px; min-width: 120px;
            }}
            QComboBox:hover {{ background-color: #3a3a5e; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox QAbstractItemView {{
                background-color: #1a1a2e; color: {TEXT_BRIGHT};
                selection-background-color: {ACCENT};
            }}
        """)
        theme_row.addWidget(self._theme_combo)
        body.addLayout(theme_row)

        lang_row = QHBoxLayout()
        lang_row.setSpacing(12)
        lang_lbl = QLabel("Language")
        lang_lbl.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {TEXT_BRIGHT}; background: transparent;")
        lang_row.addWidget(lang_lbl)
        lang_row.addStretch()
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["en", "fr", "de", "es", "ja"])
        self._lang_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 6px 12px; font-size: 12px; min-width: 120px;
            }}
            QComboBox:hover {{ background-color: #3a3a5e; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox QAbstractItemView {{
                background-color: #1a1a2e; color: {TEXT_BRIGHT};
                selection-background-color: {ACCENT};
            }}
        """)
        lang_row.addWidget(self._lang_combo)
        body.addLayout(lang_row)

        notif_row = QHBoxLayout()
        notif_row.setSpacing(12)
        self._notif_check = QCheckBox("Notifications Enabled")
        self._notif_check.setStyleSheet(f"""
            QCheckBox {{
                font-size: 13px; color: {TEXT_BRIGHT}; background: transparent; spacing: 8px;
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
        self._notif_check.setChecked(True)
        notif_row.addWidget(self._notif_check)
        notif_row.addStretch()
        body.addLayout(notif_row)

        sp_row = QHBoxLayout()
        sp_row.setSpacing(12)
        sp_lbl = QLabel("Default Search Provider")
        sp_lbl.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {TEXT_BRIGHT}; background: transparent;")
        sp_row.addWidget(sp_lbl)
        sp_row.addStretch()
        self._sp_combo = QComboBox()
        self._sp_combo.addItems(["dummy", "brave"])
        self._sp_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 6px 12px; font-size: 12px; min-width: 120px;
            }}
            QComboBox:hover {{ background-color: #3a3a5e; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox QAbstractItemView {{
                background-color: #1a1a2e; color: {TEXT_BRIGHT};
                selection-background-color: {ACCENT};
            }}
        """)
        sp_row.addWidget(self._sp_combo)
        body.addLayout(sp_row)

        mq_row = QHBoxLayout()
        mq_row.setSpacing(12)
        mq_lbl = QLabel("Default Max Queries")
        mq_lbl.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {TEXT_BRIGHT}; background: transparent;")
        mq_row.addWidget(mq_lbl)
        mq_row.addStretch()
        self._queries_spin = QSpinBox()
        self._queries_spin.setRange(1, 20)
        self._queries_spin.setValue(5)
        self._queries_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 6px 12px; font-size: 12px; min-width: 80px;
            }}
            QSpinBox:hover {{ background-color: #3a3a5e; }}
            QSpinBox::up-button, QSpinBox::down-button {{ border: none; width: 16px; }}
        """)
        mq_row.addWidget(self._queries_spin)
        body.addLayout(mq_row)

        mr_row = QHBoxLayout()
        mr_row.setSpacing(12)
        mr_lbl = QLabel("Default Max Results")
        mr_lbl.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {TEXT_BRIGHT}; background: transparent;")
        mr_row.addWidget(mr_lbl)
        mr_row.addStretch()
        self._results_spin = QSpinBox()
        self._results_spin.setRange(1, 50)
        self._results_spin.setValue(10)
        self._results_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: #2a2a44; color: {TEXT_BRIGHT}; border: none;
                border-radius: 6px; padding: 6px 12px; font-size: 12px; min-width: 80px;
            }}
            QSpinBox:hover {{ background-color: #3a3a5e; }}
            QSpinBox::up-button, QSpinBox::down-button {{ border: none; width: 16px; }}
        """)
        mr_row.addWidget(self._results_spin)
        body.addLayout(mr_row)

        save_row = QHBoxLayout()
        save_row.addStretch()
        self._save_btn = QPushButton("Save Preferences")
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT}; color: white; border: none;
                border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #6d28d9; }}
            QPushButton:disabled {{ background-color: #3a3a5e; color: #666688; }}
        """)
        self._save_btn.clicked.connect(self._save_preferences)
        save_row.addWidget(self._save_btn)

        self._save_status = QLabel("")
        self._save_status.setStyleSheet(f"font-size: 12px; color: {GREEN}; background: transparent;")
        save_row.addWidget(self._save_status)

        body.addLayout(save_row)
        self._main_layout.addWidget(section)

    def _build_digest_section(self) -> None:
        section = SettingsSection("Digest Schedule")
        body = section.body()

        lbl = QLabel(
            "Daily digest and notification scheduling is currently configured "
            "via config files (OOS_NOTIFICATIONS__*) and the .env / YAML configuration. "
            "User-level digest preferences will be available in a future release."
        )
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"font-size: 13px; color: {TEXT_MUTED}; background: transparent;")
        body.addWidget(lbl)

        self._main_layout.addWidget(section)

    def _load_all(self) -> None:
        try:
            if not self.isWidgetType() and not self.isWindow():
                return
        except RuntimeError:
            return
        self._load_system_settings()
        self._load_user_settings()

    def _load_system_settings(self) -> None:
        try:
            resp = httpx.get(f"{API_BASE}/settings", timeout=10)
            resp.raise_for_status()
            self._system_settings = resp.json()
            self._render_integrations()
        except Exception:
            pass

    def _load_user_settings(self) -> None:
        try:
            resp = httpx.get(f"{API_BASE}/user-settings?user_id={USER_ID}", timeout=10)
            if resp.status_code == 200:
                self._user_settings = resp.json()
                self._apply_user_settings()
        except Exception:
            pass

    def _apply_user_settings(self) -> None:
        if not self._user_settings:
            return
        theme = self._user_settings.get("theme", "system")
        idx = self._theme_combo.findText(theme)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)

        lang = self._user_settings.get("language", "en")
        idx = self._lang_combo.findText(lang)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)

        self._notif_check.setChecked(self._user_settings.get("notifications_enabled", True))

        sp = self._user_settings.get("default_search_provider", "dummy")
        idx = self._sp_combo.findText(sp)
        if idx >= 0:
            self._sp_combo.setCurrentIndex(idx)

        self._queries_spin.setValue(self._user_settings.get("default_max_queries", 5))
        self._results_spin.setValue(self._user_settings.get("default_max_results", 10))

    def _render_integrations(self) -> None:
        self._clear_layout(self._integration_container)
        statuses = (self._system_settings or {}).get("configuration_status", [])
        if not statuses:
            lbl = QLabel("No integration data available.")
            lbl.setStyleSheet(f"font-size: 13px; color: {TEXT_MUTED}; background: transparent;")
            self._integration_container.addWidget(lbl)
            return

        for item in statuses:
            row = QHBoxLayout()
            row.setSpacing(8)

            name = item.get("name", "unknown")
            configured = item.get("configured", False)
            env_var = item.get("env_var", "")
            hint = item.get("hint", "")

            indicator = QLabel("✅" if configured else "❌")
            indicator.setStyleSheet("background: transparent; font-size: 14px;")
            row.addWidget(indicator)

            label = QLabel(name)
            label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {TEXT_BRIGHT}; background: transparent;")
            row.addWidget(label)

            status_text = "Configured" if configured else "Not configured"
            status_lbl = QLabel(status_text)
            status_lbl.setStyleSheet(
                f"font-size: 12px; color: {GREEN}; background: transparent;"
                if configured
                else f"font-size: 12px; color: {RED}; background: transparent;"
            )
            row.addWidget(status_lbl)

            if not configured and env_var:
                env_label = QLabel(env_var)
                env_label.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; font-family: monospace; background: transparent;")
                row.addWidget(env_label)

            row.addStretch()

            if not configured and hint:
                hint_label = QLabel(hint)
                hint_label.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;")
                row.addWidget(hint_label)

            self._integration_container.addLayout(row)

    def _save_preferences(self) -> None:
        self._save_btn.setEnabled(False)
        self._save_status.setText("Saving...")
        self._save_status.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED}; background: transparent;")

        data = {
            "theme": self._theme_combo.currentText(),
            "language": self._lang_combo.currentText(),
            "notifications_enabled": self._notif_check.isChecked(),
            "default_search_provider": self._sp_combo.currentText(),
            "default_max_queries": self._queries_spin.value(),
            "default_max_results": self._results_spin.value(),
        }

        try:
            resp = httpx.put(
                f"{API_BASE}/user-settings?user_id={USER_ID}",
                json=data,
                timeout=10,
            )
            if resp.status_code == 200:
                self._save_status.setText("Saved")
                self._save_status.setStyleSheet(f"font-size: 12px; color: {GREEN}; background: transparent;")
                self._user_settings = resp.json()
            else:
                self._save_status.setText("Error saving")
                self._save_status.setStyleSheet(f"font-size: 12px; color: {RED}; background: transparent;")
        except Exception:
            self._save_status.setText("Error — server unreachable")
            self._save_status.setStyleSheet(f"font-size: 12px; color: {RED}; background: transparent;")
        finally:
            self._save_btn.setEnabled(True)
            QTimer.singleShot(3000, lambda: self._save_status.setText(""))

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
            elif item.widget():
                item.widget().deleteLater()
