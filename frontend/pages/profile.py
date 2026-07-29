"""Profile page — per-slot management with resume upload and targeting form."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from frontend.pages.base import PageWidget
from frontend.theme import (
    ACCENT,
    ACCENT_HOVER,
    ACCENT_LIGHT,
    ACCENT_MUTED_BG,
    BG_CARD,
    BG_ELEVATED,
    BORDER_SUBTLE,
    TEXT_BRIGHT,
    TEXT_MUTED,
    TEXT_SECONDARY,
    card_frame_stylesheet,
    muted_label_stylesheet,
    separator_stylesheet,
)
from frontend.user_context import get_active_user_id
from frontend.widgets.profile_form import TargetingForm

API_BASE = "http://127.0.0.1:8000/api/v1"
MAX_SLOTS = 10


# ── Slot card in the switcher strip ─────────────────────────────────────


class SlotCard(QFrame):
    """A clickable card in the slot switcher strip."""

    def __init__(
        self,
        slot_data: dict[str, Any],
        active: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._data = slot_data
        self._slot_id = slot_data.get("id", "")
        self.setObjectName("slotCard")
        border_left = ACCENT if active else "transparent"
        self.setStyleSheet(
            card_frame_stylesheet("slotCard", border_left=border_left) + """
            QFrame#slotCard:hover {
                border: 1px solid """ + ACCENT_LIGHT + """;
            }
        """
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(180)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        name_label = QLabel(slot_data.get("name", "Untitled"))
        name_label.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {TEXT_BRIGHT}; background: transparent;"
        )
        layout.addWidget(name_label)

        subtitle = self._derive_subtitle(slot_data)
        sub_label = QLabel(subtitle)
        sub_label.setWordWrap(True)
        sub_label.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;")
        layout.addWidget(sub_label)

    def _derive_subtitle(self, data: dict[str, Any]) -> str:
        skills = data.get("skills") or []
        if skills:
            return ", ".join(skills[:3]) + ("..." if len(skills) > 3 else "")
        locations = data.get("preferred_locations") or []
        if locations:
            return locations[0][:60]
        return "No details yet"

    def mousePressEvent(self, event) -> None:
        parent_widget = self.parentWidget()
        while parent_widget and not hasattr(parent_widget, "_on_slot_selected"):
            parent_widget = parent_widget.parentWidget()
        if parent_widget:
            parent_widget._on_slot_selected(self._slot_id)
        super().mousePressEvent(event)

    def slot_id(self) -> str:
        return self._slot_id


class NewSlotCard(QFrame):
    """The '+ New Slot' card at the end of the switcher strip."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("newSlotCard")
        self.setStyleSheet(f"""
            QFrame#newSlotCard {{
                background-color: {BG_ELEVATED};
                border: 2px dashed {BORDER_SUBTLE};
                border-radius: 10px;
            }}
            QFrame#newSlotCard:hover {{
                border-color: {ACCENT_LIGHT};
                background-color: {ACCENT_MUTED_BG};
            }}
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(180)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel("+ New Slot")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {ACCENT_LIGHT}; background: transparent;"
        )
        layout.addWidget(label)
        hint = QLabel("Add a job-search track")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;")
        layout.addWidget(hint)

    def set_disabled(self, disabled: bool) -> None:
        self.setEnabled(not disabled)
        if disabled:
            self.setToolTip(f"Maximum of {MAX_SLOTS} slots reached.")
            self.setStyleSheet(f"""
                QFrame#newSlotCard {{
                    background-color: {BG_CARD};
                    border: 2px dashed {BORDER_SUBTLE};
                    border-radius: 10px;
                }}
            """)
        else:
            self.setToolTip("")
            self.setStyleSheet(f"""
                QFrame#newSlotCard {{
                    background-color: {BG_ELEVATED};
                    border: 2px dashed {BORDER_SUBTLE};
                    border-radius: 10px;
                }}
                QFrame#newSlotCard:hover {{
                    border-color: {ACCENT_LIGHT};
                    background-color: {ACCENT_MUTED_BG};
                }}
            """)

    def mousePressEvent(self, event) -> None:
        if not self.isEnabled():
            return
        parent_widget = self.parentWidget()
        while parent_widget and not hasattr(parent_widget, "_on_new_slot"):
            parent_widget = parent_widget.parentWidget()
        if parent_widget:
            parent_widget._on_new_slot()
        super().mousePressEvent(event)


# ── Read-only sub-cards for parsed data ─────────────────────────────────


class SectionCard(QFrame):
    """A read-only sub-card for a data section (education/experience/projects)."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sectionCard")
        self.setStyleSheet(card_frame_stylesheet("sectionCard"))
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 12, 16, 12)
        self._layout.setSpacing(8)

        header = QLabel(title)
        header.setStyleSheet(muted_label_stylesheet(size=12, weight=600))
        self._layout.addWidget(header)

    def body(self) -> QVBoxLayout:
        return self._layout

    def clear_body(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()


def _chip(label: str) -> QLabel:
    lbl = QLabel(label)
    lbl.setStyleSheet(f"""
        QLabel {{
            background-color: #2a1a4e; color: {ACCENT_LIGHT};
            border-radius: 4px; padding: 4px 10px;
            font-size: 12px; font-weight: 500;
        }}
    """)
    return lbl


def _entry_row(items: list[str]) -> QWidget:
    row = QWidget()
    row.setStyleSheet("background: transparent;")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    for item in items:
        layout.addWidget(QLabel(item))
    return row


def _render_skills(parent: QVBoxLayout, skills: list[str]) -> None:
    if not skills:
        return
    card = SectionCard("Skills")
    chip_row = QHBoxLayout()
    chip_row.setSpacing(6)
    chip_row.setContentsMargins(0, 0, 0, 0)
    for skill in skills:
        chip_row.addWidget(_chip(skill))
    chip_row.addStretch()
    card.body().addLayout(chip_row)
    parent.addWidget(card)


def _render_education(parent: QVBoxLayout, education: list[dict[str, Any]]) -> None:
    if not education:
        return
    card = SectionCard("Education")
    for entry in education:
        text = f"{entry.get('institution', '')} — {entry.get('degree', '')}"
        if entry.get("field"):
            text += f" in {entry['field']}"
        dates = f"{entry.get('start_date', '')} – {entry.get('end_date', '')}"
        full = f"{text}  ({dates})" if dates else text
        lbl = QLabel(full)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"font-size: 13px; color: {TEXT_BRIGHT}; background: transparent;")
        card.body().addWidget(lbl)
    parent.addWidget(card)


def _render_experience(parent: QVBoxLayout, experience: list[dict[str, Any]]) -> None:
    if not experience:
        return
    card = SectionCard("Experience")
    for entry in experience:
        text = f"{entry.get('role', '')} @ {entry.get('company', '')}"
        dates = f"{entry.get('start_date', '')} – {entry.get('end_date', '')}"
        full = f"{text}  ({dates})" if dates else text
        lbl = QLabel(full)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"font-size: 13px; color: {TEXT_BRIGHT}; background: transparent;")
        card.body().addWidget(lbl)
        desc = (entry.get("description") or "").strip()
        if desc:
            dl = QLabel(desc[:120])
            dl.setWordWrap(True)
            dl.setStyleSheet(
                f"font-size: 12px; color: {TEXT_SECONDARY}; background: transparent; padding-left: 8px;"
            )
            card.body().addWidget(dl)
    parent.addWidget(card)


def _render_projects(parent: QVBoxLayout, projects: list[dict[str, Any]]) -> None:
    if not projects:
        return
    card = SectionCard("Projects")
    for entry in projects:
        text = entry.get("name", "")
        tech = entry.get("technologies", "")
        full = f"{text}  —  {tech}" if tech else text
        lbl = QLabel(full)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"font-size: 13px; color: {TEXT_BRIGHT}; background: transparent;")
        card.body().addWidget(lbl)
    parent.addWidget(card)


# ── Profile page ────────────────────────────────────────────────────────


class ProfilePage(PageWidget):
    """Slot-based profile management page."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self._slots: list[dict[str, Any]] = []
        self._active_slot_id: str | None = None
        self._targeting_form: TargetingForm | None = None
        self._switcher_widget: QWidget | None = None
        self._empty_widget: QWidget | None = None
        self._content_area: QWidget | None = None
        self._resume_section: QWidget | None = None
        self._parsed_section: QVBoxLayout | None = None
        super().__init__("Profile", parent)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(0)

        header = QLabel("Profile")
        header.setStyleSheet("""
            QLabel {
                font-size: 24px; font-weight: 600;
                color: #f0f0ff; padding-bottom: 4px;
            }
        """)
        layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("QFrame { color: #2a2a44; max-height: 1px; }")
        layout.addWidget(sep)
        layout.addSpacing(16)

        self._switcher_widget = QWidget()
        self._switcher_widget.setStyleSheet("background: transparent;")
        self._switcher_widget.setLayout(QVBoxLayout())
        self._switcher_widget.setVisible(False)
        layout.addWidget(self._switcher_widget)

        self._empty_widget = QWidget()
        self._empty_widget.setStyleSheet("background: transparent;")
        self._empty_widget.setLayout(QVBoxLayout())
        self._empty_widget.setVisible(False)
        layout.addWidget(self._empty_widget, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._content_area = QWidget()
        self._content_area.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content_area)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(20)
        scroll.setWidget(self._content_area)
        self._content_area.setVisible(False)
        layout.addWidget(scroll, 1)

        self._build_empty_state()
        self._build_switcher()

        self._fetch_slots()

    def _clear_layout(self, layout: QVBoxLayout | None) -> None:
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    # ── switcher ─────────────────────────────────────────────────────────

    def _build_switcher(self) -> None:
        pass

    def _rebuild_switcher(self) -> None:
        if not self._switcher_widget:
            return
        layout = self._switcher_widget.layout()
        self._clear_layout(layout)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(8)

        label = QLabel("Job-Search Slots")
        label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {TEXT_SECONDARY}; background: transparent;"
        )
        layout.addWidget(label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(110)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(inner)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)

        for slot in self._slots:
            card = SlotCard(slot, active=slot.get("id") == self._active_slot_id)
            row_layout.addWidget(card)

        self._new_slot_card = NewSlotCard()
        self._new_slot_card.set_disabled(len(self._slots) >= MAX_SLOTS)
        row_layout.addWidget(self._new_slot_card)

        row_layout.addStretch(1)
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        self._switcher_widget.setVisible(True)

    # ── empty state ──────────────────────────────────────────────────────

    def _build_empty_state(self) -> None:
        if not self._empty_widget:
            return
        layout = self._empty_widget.layout()
        self._clear_layout(layout)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        title = QLabel("Create Your First Slot")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"font-size: 20px; font-weight: 700; color: {TEXT_BRIGHT}; background: transparent;"
        )
        layout.addWidget(title)

        desc = QLabel(
            "A slot represents a job-search track.\n"
            "Upload a resume to auto-fill your details, or fill in targeting info manually."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size: 13px; color: {TEXT_MUTED}; background: transparent;")
        layout.addWidget(desc)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(24)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        upload_btn = QPushButton("Upload Resume")
        upload_btn.setFixedSize(200, 80)
        upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        upload_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT}; color: white; border: none;
                border-radius: 12px; font-size: 15px; font-weight: 700;
            }}
            QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
        """)
        upload_btn.clicked.connect(self._on_upload_resume)
        btn_row.addWidget(upload_btn)

        manual_btn = QPushButton("Fill Manually")
        manual_btn.setFixedSize(200, 80)
        manual_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        manual_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {BG_ELEVATED}; color: {TEXT_BRIGHT};
                border: 2px solid {BORDER_SUBTLE}; border-radius: 12px;
                font-size: 15px; font-weight: 700;
            }}
            QPushButton:hover {{
                border-color: {ACCENT_LIGHT};
                background-color: {ACCENT_MUTED_BG};
            }}
        """)
        manual_btn.clicked.connect(self._on_fill_manual)
        btn_row.addWidget(manual_btn)

        layout.addLayout(btn_row)

    # ── content area ─────────────────────────────────────────────────────

    def _build_content(self) -> None:
        if not self._content_layout:
            return
        self._clear_layout(self._content_layout)

        # Resume upload section
        self._resume_section = QWidget()
        self._resume_section.setStyleSheet("background: transparent;")
        self._content_layout.addWidget(self._resume_section)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(separator_stylesheet(margin_h=0))
        self._content_layout.addWidget(sep)

        # Parsed data section (read-only)
        parsed_header = QLabel("Parsed Resume Data")
        parsed_header.setStyleSheet(
            f"font-size: 16px; font-weight: 600; color: {TEXT_BRIGHT}; background: transparent;"
        )
        self._content_layout.addWidget(parsed_header)

        self._parsed_section = QVBoxLayout()
        self._parsed_section.setSpacing(12)
        self._parsed_section.setContentsMargins(0, 0, 0, 0)
        self._content_layout.addLayout(self._parsed_section)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(separator_stylesheet(margin_h=0))
        self._content_layout.addWidget(sep2)

        # Targeting form
        targeting_header = QLabel("Targeting")
        targeting_header.setStyleSheet(
            f"font-size: 16px; font-weight: 600; color: {TEXT_BRIGHT}; background: transparent;"
        )
        self._content_layout.addWidget(targeting_header)

        self._targeting_form = TargetingForm()
        self._content_layout.addWidget(self._targeting_form)

        self._content_layout.addStretch(1)

    def _rebuild_resume_section(self, slot_data: dict[str, Any]) -> None:
        if not self._resume_section:
            return
        layout = self._resume_section.layout()
        if layout:
            self._clear_layout(layout)
        else:
            layout = QHBoxLayout(self._resume_section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(12)

        resume_file = slot_data.get("resume_filename")
        if resume_file:
            info = QLabel(f"Resume: {resume_file}")
            info.setStyleSheet(
                f"font-size: 13px; color: {TEXT_SECONDARY}; background: transparent;"
            )
            layout.addWidget(info)
            layout.addStretch()
            re_up = QPushButton("Re-upload Resume")
            re_up.setStyleSheet(f"""
                QPushButton {{
                    background-color: {BG_ELEVATED}; color: {TEXT_BRIGHT};
                    border: 1px solid {BORDER_SUBTLE}; border-radius: 6px;
                    padding: 8px 16px; font-size: 12px; font-weight: 600;
                }}
                QPushButton:hover {{
                    border-color: {ACCENT_LIGHT};
                    background-color: {ACCENT_MUTED_BG};
                }}
            """)
            re_up.clicked.connect(self._on_upload_resume)
            layout.addWidget(re_up)
        else:
            info = QLabel("No resume uploaded yet. Upload a resume to auto-fill skills, education, and experience.")
            info.setWordWrap(True)
            info.setStyleSheet(
                f"font-size: 13px; color: {TEXT_MUTED}; background: transparent;"
            )
            layout.addWidget(info, 1)
            up_btn = QPushButton("Upload Resume")
            up_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ACCENT}; color: white; border: none;
                    border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
            """)
            up_btn.clicked.connect(self._on_upload_resume)
            layout.addWidget(up_btn)

    def _rebuild_parsed_data(self, slot_data: dict[str, Any]) -> None:
        if not self._parsed_section:
            return
        self._clear_layout(self._parsed_section)

        skills = slot_data.get("skills") or []
        education = slot_data.get("education") or []
        experience = slot_data.get("experience") or []
        projects = slot_data.get("projects") or []

        if not any([skills, education, experience, projects]):
            empty = QLabel("No parsed resume data. Upload a resume to populate this section.")
            empty.setWordWrap(True)
            empty.setStyleSheet(
                f"font-size: 13px; color: {TEXT_MUTED}; background: transparent; padding: 8px 0;"
            )
            self._parsed_section.addWidget(empty)
            return

        _render_skills(self._parsed_section, skills)
        _render_education(self._parsed_section, education)
        _render_experience(self._parsed_section, experience)
        _render_projects(self._parsed_section, projects)

    # ── API calls ────────────────────────────────────────────────────────

    def _fetch_slots(self) -> None:
        uid = get_active_user_id()
        try:
            resp = httpx.get(f"{API_BASE}/users/{uid}/profiles", timeout=10)
            resp.raise_for_status()
            self._slots = resp.json()
        except httpx.HTTPError:
            self._slots = []
        self._sync_ui()

    def _sync_ui(self) -> None:
        if not self._slots:
            self._switcher_widget.setVisible(False)
            self._content_area.setVisible(False)
            self._build_empty_state()
            self._empty_widget.setVisible(True)
        else:
            self._empty_widget.setVisible(False)
            self._rebuild_switcher()
            self._switcher_widget.setVisible(True)

            if not self._active_slot_id or self._active_slot_id not in {p.get("id") for p in self._slots}:
                self._active_slot_id = self._slots[0].get("id")

            self._load_slot_into_view(self._active_slot_id)
            self._content_area.setVisible(True)

    def _load_slot_into_view(self, slot_id: str | None) -> None:
        if not slot_id:
            return
        try:
            resp = httpx.get(f"{API_BASE}/profiles/id/{slot_id}", timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError:
            QMessageBox.warning(self, "Error", "Failed to load slot data.")
            return

        self._build_content()
        self._rebuild_resume_section(data)
        self._rebuild_parsed_data(data)
        if self._targeting_form:
            self._targeting_form.set_slot_id(slot_id)
            self._targeting_form.populate(data)

    # ── callbacks ────────────────────────────────────────────────────────

    def _on_slot_selected(self, slot_id: str) -> None:
        if slot_id == self._active_slot_id:
            return
        self._active_slot_id = slot_id
        self._rebuild_switcher()
        self._load_slot_into_view(slot_id)

    def _on_slot_deleted(self, slot_id: str) -> None:
        self._slots = [p for p in self._slots if p.get("id") != slot_id]
        if self._active_slot_id == slot_id:
            self._active_slot_id = None
        self._sync_ui()

    def _on_new_slot(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("New Slot")
        dialog.setMinimumWidth(480)
        dialog.setStyleSheet("""
            QDialog { background-color: #12121f; color: #e4e4f0; }
        """)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("How would you like to set up this slot?")
        title.setWordWrap(True)
        title.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #f0f0ff; background: transparent;"
        )
        layout.addWidget(title)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)

        action = [None]

        upload_btn = QPushButton("Upload Resume")
        upload_btn.setFixedSize(200, 100)
        upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        upload_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT}; color: white; border: none;
                border-radius: 12px; font-size: 15px; font-weight: 700;
            }}
            QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
        """)
        upload_btn.clicked.connect(lambda: (action.__setitem__(0, "upload"), dialog.accept()))
        btn_row.addWidget(upload_btn)

        manual_btn = QPushButton("Fill Manually")
        manual_btn.setFixedSize(200, 100)
        manual_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        manual_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {BG_ELEVATED}; color: {TEXT_BRIGHT};
                border: 2px solid {BORDER_SUBTLE}; border-radius: 12px;
                font-size: 15px; font-weight: 700;
            }}
            QPushButton:hover {{
                border-color: {ACCENT_LIGHT};
                background-color: {ACCENT_MUTED_BG};
            }}
        """)
        manual_btn.clicked.connect(lambda: (action.__setitem__(0, "manual"), dialog.accept()))
        btn_row.addWidget(manual_btn)

        layout.addLayout(btn_row)
        layout.addStretch(1)

        result = dialog.exec()
        if result != QDialog.DialogCode.Accepted or action[0] is None:
            return
        if action[0] == "upload":
            self._on_upload_resume()
        elif action[0] == "manual":
            self._on_fill_manual()

    def _on_upload_resume(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Resume", "", "Resume Files (*.pdf *.docx *.tex)",
        )
        if not path:
            return
        file_path = Path(path)
        if not file_path.exists():
            QMessageBox.warning(self, "Error", "File not found.")
            return

        try:
            with open(path, "rb") as f:
                files = {"file": (file_path.name, f.read(), "application/octet-stream")}
            resp = httpx.post(f"{API_BASE}/resume/parse", files=files, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            data["_parsed_filename"] = file_path.name

            self._show_parsed_data_dialog(data)

            name_suggestion = self._derive_name_from_parsed(data)
            self._show_create_form(data, name_suggestion)
        except httpx.HTTPError as e:
            QMessageBox.critical(self, "Error", f"Parse failed:\n{e}")

    def _show_parsed_data_dialog(self, data: dict) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Parsed Resume Data")
        dialog.setGeometry(100, 100, 700, 600)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #0f0f2e;
                color: #e0e0ff;
            }
            QTabWidget::pane {
                border: 1px solid #2e1a47;
            }
            QTabBar::tab {
                background-color: #1a0f3a;
                color: #8888bb;
                padding: 6px 16px;
                margin-right: 2px;
                border: 1px solid #2e1a47;
            }
            QTabBar::tab:selected {
                background-color: #2e1a5f;
                color: #e0e0ff;
                border-bottom: 2px solid #7c3aed;
            }
            QTextEdit {
                background-color: #1a0f3a;
                color: #e0e0ff;
                border: 1px solid #2e1a47;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        tabs = QTabWidget()
        
        # Skills tab
        skills_text = QTextEdit()
        skills_text.setReadOnly(True)
        skills_list = data.get("skills", [])
        skills_text.setText("\n".join(skills_list) if skills_list else "No skills found")
        tabs.addTab(skills_text, f"Skills ({len(skills_list)})")
        
        # Education tab
        edu_text = QTextEdit()
        edu_text.setReadOnly(True)
        edu_list = data.get("education", [])
        edu_content = "\n\n".join([
            f"📚 {e.get('degree', 'N/A')} in {e.get('field', 'N/A')}\n"
            f"Institution: {e.get('institution', 'N/A')}\n"
            f"Period: {e.get('start_date', '?')} - {e.get('end_date', '?')}"
            for e in edu_list
        ])
        edu_text.setText(edu_content if edu_list else "No education found")
        tabs.addTab(edu_text, f"Education ({len(edu_list)})")
        
        # Experience tab
        exp_text = QTextEdit()
        exp_text.setReadOnly(True)
        exp_list = data.get("experience", [])
        exp_content = "\n\n".join([
            f"💼 {e.get('role', 'N/A')} @ {e.get('company', 'N/A')}\n"
            f"Period: {e.get('start_date', '?')} - {e.get('end_date', '?')}\n"
            f"Description: {e.get('description', 'N/A')}"
            for e in exp_list
        ])
        exp_text.setText(exp_content if exp_list else "No experience found")
        tabs.addTab(exp_text, f"Experience ({len(exp_list)})")
        
        # Projects tab
        proj_text = QTextEdit()
        proj_text.setReadOnly(True)
        proj_list = data.get("projects", [])
        proj_content = "\n\n".join([
            f"🚀 {p.get('name', 'N/A')}\n"
            f"Technologies: {p.get('technologies', 'N/A')}\n"
            f"Description: {p.get('description', 'N/A')}\n"
            f"URL: {p.get('url', 'N/A')}"
            for p in proj_list
        ])
        proj_text.setText(proj_content if proj_list else "No projects found")
        tabs.addTab(proj_text, f"Projects ({len(proj_list)})")
        
        layout.addWidget(tabs)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        close_btn.setStyleSheet("background-color: #7c3aed; color: white; padding: 8px 16px; border-radius: 4px;")
        layout.addWidget(close_btn)
        
        dialog.exec()

    def _build_buttons(self, parent_layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 16, 0, 0)
        row.setSpacing(12)
        save_btn = self._styled_button("Save Profile", "#7c3aed")
        save_btn.clicked.connect(self._save_profile)
        del_btn = self._styled_button("Delete Profile", "#7f1d1d")
        del_btn.clicked.connect(self._delete_profile)
        row.addStretch(1)
        row.addWidget(del_btn)
        row.addWidget(save_btn)
        parent_layout.addLayout(row)

    # ── education / experience dialogs ─────────────────────────────────

    def _show_entry_dialog(
        self, title: str, fields: list[tuple[str, str]],
    ) -> dict[str, str] | None:
        dialog = QWidget(None, Qt.WindowType.Dialog)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(400)
        dialog.setStyleSheet("""
            QWidget {
                background-color: #1a1a2e;
                color: #e4e4f0;
                font-size: 13px;
            }
            QLineEdit {
                padding: 6px 10px;
                border: 1px solid #2a2a44;
                border-radius: 6px;
                background-color: #0f0f1a;
                color: #e4e4f0;
            }
            QLineEdit:focus { border-color: #7c3aed; }
            QPushButton {
                padding: 6px 16px;
                border: none;
                border-radius: 6px;
                font-weight: 600;
                color: #e4e4f0;
            }
        """)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        widgets: dict[str, QLineEdit] = {}
        for label, placeholder in fields:
            le = QLineEdit()
            le.setPlaceholderText(placeholder)
            form.addRow(f"{label}:", le)
            widgets[label] = le
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet("background-color: #252540;")
        cancel.clicked.connect(dialog.close)
        ok = QPushButton("OK")
        ok.setStyleSheet("background-color: #7c3aed;")
        result: dict[str, str] | None = None

        def on_ok() -> None:
            nonlocal result
            result = {k: w.text() for k, w in widgets.items()}
            dialog.close()

        ok.clicked.connect(on_ok)
        btn_row.addStretch(1)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        layout.addLayout(btn_row)
        dialog.setLayout(layout)
        dialog.exec()
        return result

    def _add_education(self) -> None:
        result = self._show_entry_dialog("Add Education", [
            ("Institution", "MIT"),
            ("Degree", "B.S."),
            ("Field", "Computer Science"),
            ("Start Date", "2018-09"),
            ("End Date", "2022-06"),
        ])
        if result and result.get("Institution"):
            text = f"{result['Institution']} - {result['Degree']} in {result['Field']} ({result['Start Date']} - {result['End Date']})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, result)
            self._edu_list.addItem(item)

    def _add_experience(self) -> None:
        result = self._show_entry_dialog("Add Experience", [
            ("Company", "Google"),
            ("Role", "Software Engineer"),
            ("Description", "Worked on..."),
            ("Start Date", "2022-07"),
            ("End Date", "present"),
        ])
        if result and result.get("Company"):
            text = f"{result['Role']} @ {result['Company']} ({result['Start Date']} - {result['End Date']})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, result)
            self._exp_list.addItem(item)

    def _remove_list_item(self, lst: QListWidget) -> None:
        for item in lst.selectedItems():
            lst.takeItem(lst.row(item))

    # ── API operations ─────────────────────────────────────────────────

    def _get_user_id(self) -> str | None:
        uid = self._user_id_input.text().strip()
        if not uid:
            QMessageBox.warning(self, "Error", "Enter a User ID")
            return None
        return uid

    def _load_profile(self) -> None:
        QMessageBox.information(
            self, "Info",
            "Use 'Upload Resume' or 'Fill Manually' to create a new slot.",
        )

    def _derive_name_from_parsed(self, data: dict[str, Any]) -> str:
        exp = data.get("experience") or []
        if exp and exp[0].get("role"):
            return exp[0]["role"].strip()[:60]
        skills = data.get("skills") or []
        if skills:
            return f"{skills[0].strip()[:40]} Track"
        return ""

    def _on_fill_manual(self) -> None:
        self._show_create_form({}, "")

    def _show_create_form(
        self, prefill: dict[str, Any], name_suggestion: str,
    ) -> None:
        self._empty_widget.setVisible(False)
        self._switcher_widget.setVisible(False)
        self._content_area.setVisible(False)

        self._build_content()

        parsed_data = {
            "skills": prefill.get("skills"),
            "education": prefill.get("education"),
            "experience": prefill.get("experience"),
            "projects": prefill.get("projects"),
        }
        self._rebuild_parsed_data(parsed_data)

        if self._targeting_form:
            self._targeting_form.set_slot_id(None)
            self._targeting_form.populate(prefill)
            name = name_suggestion or None
            if name and self._targeting_form._name:
                self._targeting_form._name.setText(name)

        self._content_area.setVisible(True)

    def _on_slot_saved(self, slot_id: str | None) -> None:
        self._active_slot_id = slot_id
        self._fetch_slots()
