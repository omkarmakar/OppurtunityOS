"""Profile management page with full CRUD form."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import httpx
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from frontend.pages.base import PageWidget
from frontend.user_context import get_active_user_id

API_BASE = "http://127.0.0.1:8000/api/v1"
DEFAULT_USER_ID = get_active_user_id()


class TagInput(QWidget):
    """A tag/chip input widget for lists of strings."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tags: list[str] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        input_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type and press Enter...")
        self._input.setStyleSheet("""
            QLineEdit {
                padding: 6px 10px;
                border: 1px solid #2a2a44;
                border-radius: 6px;
                background-color: #1a1a2e;
                color: #e4e4f0;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #7c3aed;
            }
        """)
        self._input.returnPressed.connect(self._add_tag)
        add_btn = QPushButton("+")
        add_btn.setFixedWidth(32)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e1065;
                color: #a78bfa;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                padding: 4px;
            }
            QPushButton:hover { background-color: #4c1d95; }
        """)
        add_btn.clicked.connect(self._add_tag)
        input_row.addWidget(self._input, 1)
        input_row.addWidget(add_btn)
        layout.addLayout(input_row)

        self._list = QListWidget()
        self._list.setMaximumHeight(120)
        self._list.setStyleSheet("""
            QListWidget {
                border: 1px solid #2a2a44;
                border-radius: 6px;
                background-color: #1a1a2e;
                color: #e4e4f0;
                font-size: 13px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 4px 8px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #252540;
            }
        """)
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
        item = self._list.itemAt(event.position().toPoint())
        if item and "\u2716" in item.text():
            idx = self._list.row(item)
            self._list.takeItem(idx)
            if idx < len(self._tags):
                self._tags.pop(idx)
        super().mousePressEvent(event)


class ProfileFormSection(QGroupBox):
    """A styled collapsible section for profile fields."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.setStyleSheet("""
            QGroupBox {
                font-size: 15px;
                font-weight: 600;
                color: #c0c0e0;
                border: 1px solid #2a2a44;
                border-radius: 8px;
                margin-top: 16px;
                padding: 20px 16px 16px 16px;
                background-color: #14142a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 12px;
                background-color: #1e1e38;
                border-radius: 4px;
                color: #a78bfa;
            }
        """)


class ProfilePage(PageWidget):
    """Profile management page with complete CRUD form."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self._profile_id: str | None = None
        super().__init__("Profile", parent)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(0)

        header = QLabel("Profile")
        header.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 600;
                color: #f0f0ff;
                padding-bottom: 4px;
            }
        """)
        layout.addWidget(header)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("QFrame { color: #2a2a44; max-height: 1px; }")
        layout.addWidget(separator)
        layout.addSpacing(16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: transparent; }
            QScrollArea > QWidget > QWidget { background-color: transparent; }
        """)

        content = QWidget()
        content.setObjectName("profileContent")
        content.setStyleSheet("QWidget#profileContent { background-color: transparent; }")
        form_layout = QVBoxLayout(content)
        form_layout.setSpacing(8)
        form_layout.setContentsMargins(0, 0, 0, 0)

        self._build_user_id_row(form_layout)
        self._build_basic_info(form_layout)
        self._build_education(form_layout)
        self._build_experience(form_layout)
        self._build_skills(form_layout)
        self._build_locations(form_layout)
        self._build_companies(form_layout)
        self._build_keywords(form_layout)
        self._build_salary(form_layout)
        self._build_links(form_layout)
        self._build_resume_upload(form_layout)
        self._build_buttons(form_layout)

        form_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

    # ── field helpers ──────────────────────────────────────────────────

    def _line_edit(self, placeholder: str = "") -> QLineEdit:
        le = QLineEdit()
        le.setPlaceholderText(placeholder)
        le.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #2a2a44;
                border-radius: 6px;
                background-color: #1a1a2e;
                color: #e4e4f0;
                font-size: 13px;
            }
            QLineEdit:focus { border-color: #7c3aed; }
        """)
        return le

    def _text_edit(self) -> QTextEdit:
        te = QTextEdit()
        te.setMaximumHeight(100)
        te.setStyleSheet("""
            QTextEdit {
                padding: 8px 12px;
                border: 1px solid #2a2a44;
                border-radius: 6px;
                background-color: #1a1a2e;
                color: #e4e4f0;
                font-size: 13px;
            }
            QTextEdit:focus { border-color: #7c3aed; }
        """)
        return te

    def _styled_button(self, text: str, color: str = "#7c3aed") -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                padding: 8px 20px;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                color: #e4e4f0;
                background-color: {color};
            }}
            QPushButton:hover {{ opacity: 0.8; }}
        """)
        return btn

    # ── build sections ─────────────────────────────────────────────────

    def _build_user_id_row(self, parent_layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        label = QLabel("User ID:")
        label.setStyleSheet("font-size: 13px; color: #8888bb;")
        self._user_id_input = self._line_edit("UUID or email")
        self._user_id_input.setText(DEFAULT_USER_ID)
        load_btn = self._styled_button("Load", "#2e1065")
        load_btn.clicked.connect(self._load_profile)
        new_btn = self._styled_button("New", "#1e3a5f")
        new_btn.clicked.connect(self._new_profile)
        row.addWidget(label)
        row.addWidget(self._user_id_input, 1)
        row.addWidget(load_btn)
        row.addWidget(new_btn)
        parent_layout.addLayout(row)

    def _build_basic_info(self, parent_layout: QVBoxLayout) -> None:
        section = ProfileFormSection("Basic Information")
        form = QFormLayout(section)
        form.setSpacing(8)

        self._display_name = self._line_edit("Display name")
        form.addRow("Name:", self._display_name)

        self._bio = self._text_edit()
        form.addRow("Bio:", self._bio)

        self._avatar_url = self._line_edit("https://...")
        form.addRow("Avatar URL:", self._avatar_url)

        parent_layout.addWidget(section)

    def _build_education(self, parent_layout: QVBoxLayout) -> None:
        section = ProfileFormSection("Education")
        layout = QVBoxLayout(section)
        self._edu_list = QListWidget()
        self._edu_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #2a2a44;
                border-radius: 6px;
                background-color: #1a1a2e;
                color: #e4e4f0;
                font-size: 13px;
            }
            QListWidget::item { padding: 6px; }
        """)
        layout.addWidget(self._edu_list)
        btn_row = QHBoxLayout()
        add_btn = self._styled_button("+ Add Education", "#2e1065")
        add_btn.clicked.connect(self._add_education)
        rm_btn = self._styled_button("Remove Selected", "#7f1d1d")
        rm_btn.clicked.connect(lambda: self._remove_list_item(self._edu_list))
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        parent_layout.addWidget(section)

    def _build_experience(self, parent_layout: QVBoxLayout) -> None:
        section = ProfileFormSection("Experience")
        layout = QVBoxLayout(section)
        self._exp_list = QListWidget()
        self._exp_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #2a2a44;
                border-radius: 6px;
                background-color: #1a1a2e;
                color: #e4e4f0;
                font-size: 13px;
            }
            QListWidget::item { padding: 6px; }
        """)
        layout.addWidget(self._exp_list)
        btn_row = QHBoxLayout()
        add_btn = self._styled_button("+ Add Experience", "#2e1065")
        add_btn.clicked.connect(self._add_experience)
        rm_btn = self._styled_button("Remove Selected", "#7f1d1d")
        rm_btn.clicked.connect(lambda: self._remove_list_item(self._exp_list))
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        parent_layout.addWidget(section)

    def _build_skills(self, parent_layout: QVBoxLayout) -> None:
        section = ProfileFormSection("Skills")
        layout = QVBoxLayout(section)
        self._skills = TagInput()
        layout.addWidget(self._skills)
        parent_layout.addWidget(section)

    def _build_locations(self, parent_layout: QVBoxLayout) -> None:
        section = ProfileFormSection("Preferred Locations")
        layout = QVBoxLayout(section)
        self._locations = TagInput()
        layout.addWidget(self._locations)
        parent_layout.addWidget(section)

    def _build_companies(self, parent_layout: QVBoxLayout) -> None:
        section = ProfileFormSection("Target Companies")
        layout = QVBoxLayout(section)
        self._companies = TagInput()
        layout.addWidget(self._companies)
        parent_layout.addWidget(section)

    def _build_keywords(self, parent_layout: QVBoxLayout) -> None:
        section = ProfileFormSection("Keywords")
        layout = QVBoxLayout(section)
        self._keywords = TagInput()
        layout.addWidget(self._keywords)
        parent_layout.addWidget(section)

    def _build_salary(self, parent_layout: QVBoxLayout) -> None:
        section = ProfileFormSection("Salary Expectations")
        layout = QVBoxLayout(section)
        self._salary = self._line_edit("e.g. 120k-150k")
        layout.addWidget(self._salary)
        parent_layout.addWidget(section)

    def _build_links(self, parent_layout: QVBoxLayout) -> None:
        section = ProfileFormSection("Links & Documents")
        form = QFormLayout(section)
        form.setSpacing(8)
        self._resume_path = self._line_edit("/path/to/resume.pdf")
        form.addRow("Resume:", self._resume_path)
        self._linkedin = self._line_edit("https://linkedin.com/in/...")
        form.addRow("LinkedIn:", self._linkedin)
        self._github = self._line_edit("https://github.com/...")
        form.addRow("GitHub:", self._github)
        self._portfolio = self._line_edit("https://...")
        form.addRow("Portfolio:", self._portfolio)
        parent_layout.addWidget(section)

    def _build_resume_upload(self, parent_layout: QVBoxLayout) -> None:
        section = ProfileFormSection("Resume Parser")
        layout = QVBoxLayout(section)

        desc = QLabel(
            "Upload a PDF or DOCX resume to auto-fill skills, projects, "
            "education, and experience."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 12px; color: #8888bb; padding-bottom: 8px;")
        layout.addWidget(desc)

        row = QHBoxLayout()
        self._resume_path_input = self._line_edit("Select a resume file...")
        self._resume_path_input.setReadOnly(True)
        browse_btn = self._styled_button("Browse", "#2e1065")
        browse_btn.clicked.connect(self._browse_resume)
        parse_btn = self._styled_button("Parse & Fill", "#7c3aed")
        parse_btn.clicked.connect(self._parse_resume)
        row.addWidget(self._resume_path_input, 1)
        row.addWidget(browse_btn)
        row.addWidget(parse_btn)
        layout.addLayout(row)

        parent_layout.addWidget(section)

    def _browse_resume(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Resume", "", "Resumes (*.pdf *.docx)",
        )
        if path:
            self._resume_path_input.setText(path)

    def _parse_resume(self) -> None:
        path = self._resume_path_input.text()
        if not path or not Path(path).exists():
            QMessageBox.warning(self, "Error", "Select a valid resume file first.")
            return

        try:
            with open(path, "rb") as f:
                files = {"file": (Path(path).name, f.read(), "application/octet-stream")}
            resp = httpx.post(f"{API_BASE}/resume/parse", files=files, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if data.get("skills"):
                self._skills.set_tags(data["skills"])
            if data.get("education"):
                self._edu_list.clear()
                for e in data["education"]:
                    text = f"{e.get('institution','')} - {e.get('degree','')} in {e.get('field','')} ({e.get('start_date','')} - {e.get('end_date','')})"
                    item = QListWidgetItem(text)
                    item.setData(Qt.ItemDataRole.UserRole, e)
                    self._edu_list.addItem(item)
            if data.get("experience"):
                self._exp_list.clear()
                for e in data["experience"]:
                    text = f"{e.get('role','')} @ {e.get('company','')} ({e.get('start_date','')} - {e.get('end_date','')})"
                    item = QListWidgetItem(text)
                    item.setData(Qt.ItemDataRole.UserRole, e)
                    self._exp_list.addItem(item)
            if data.get("projects"):
                for p in data["projects"]:
                    text = f"[Project] {p.get('name','')} - {p.get('technologies','')}"
                    item = QListWidgetItem(text)
                    item.setData(Qt.ItemDataRole.UserRole, p)
                    self._exp_list.addItem(item)

            # Show detailed parsed data dialog
            self._show_parsed_data_dialog(data)
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
        uid = self._get_user_id()
        if not uid:
            return
        try:
            resp = httpx.get(f"{API_BASE}/profiles/{uid}", timeout=10)
            if resp.status_code == 404:
                QMessageBox.information(self, "Not Found", "No profile found for this user.")
                self._clear_form()
                return
            resp.raise_for_status()
            self._populate_form(resp.json())
            self._profile_id = resp.json()["id"]
        except httpx.HTTPError as e:
            QMessageBox.critical(self, "Error", f"Failed to load profile:\n{e}")

    def _new_profile(self) -> None:
        self._clear_form()
        self._profile_id = None

    def _save_profile(self) -> None:
        uid = self._get_user_id()
        if not uid:
            return
        data = self._collect_form_data()
        try:
            existing_resp = httpx.get(f"{API_BASE}/profiles/{uid}", timeout=10)
            if existing_resp.status_code == 200:
                resp = httpx.put(f"{API_BASE}/profiles/{uid}", json=data, timeout=10)
                resp.raise_for_status()
                QMessageBox.information(self, "Saved", "Profile updated successfully.")
            else:
                data["user_id"] = uid
                resp = httpx.post(f"{API_BASE}/profiles", json=data, timeout=10)
                resp.raise_for_status()
                QMessageBox.information(self, "Created", "Profile created successfully.")
            self._profile_id = resp.json()["id"]
            self._populate_form(resp.json())
        except httpx.HTTPError as e:
            QMessageBox.critical(self, "Error", f"Failed to save profile:\n{e}")

    def _delete_profile(self) -> None:
        uid = self._get_user_id()
        if not uid:
            return
        confirm = QMessageBox.question(
            self, "Confirm Delete", "Delete this profile?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            resp = httpx.delete(f"{API_BASE}/profiles/{uid}", timeout=10)
            if resp.status_code == 204:
                QMessageBox.information(self, "Deleted", "Profile deleted.")
                self._clear_form()
            else:
                QMessageBox.warning(self, "Error", f"Unexpected response: {resp.status_code}")
        except httpx.HTTPError as e:
            QMessageBox.critical(self, "Error", f"Failed to delete profile:\n{e}")

    # ── form population / collection ───────────────────────────────────

    def _populate_form(self, data: dict[str, Any]) -> None:
        self._display_name.setText(data.get("display_name") or "")
        self._bio.setPlainText(data.get("bio") or "")
        self._avatar_url.setText(data.get("avatar_url") or "")
        self._salary.setText(data.get("salary_expectations") or "")
        self._resume_path.setText(data.get("resume_path") or "")
        self._linkedin.setText(data.get("linkedin_url") or "")
        self._github.setText(data.get("github_url") or "")
        self._portfolio.setText(data.get("portfolio") or "")

        self._skills.set_tags(data.get("skills") or [])
        self._locations.set_tags(data.get("preferred_locations") or [])
        self._companies.set_tags(data.get("target_companies") or [])
        self._keywords.set_tags(data.get("keywords") or [])
        self._user_id_input.setText(str(data.get("user_id", self._user_id_input.text())))

        self._edu_list.clear()
        for entry in data.get("education") or []:
            text = f"{entry.get('institution','')} - {entry.get('degree','')} in {entry.get('field','')} ({entry.get('start_date','')} - {entry.get('end_date','')})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._edu_list.addItem(item)

        self._exp_list.clear()
        for entry in data.get("experience") or []:
            text = f"{entry.get('role','')} @ {entry.get('company','')} ({entry.get('start_date','')} - {entry.get('end_date','')})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._exp_list.addItem(item)

    def _collect_form_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        fields = {
            "display_name": self._display_name.text(),
            "avatar_url": self._avatar_url.text(),
            "bio": self._bio.toPlainText(),
            "salary_expectations": self._salary.text(),
            "resume_path": self._resume_path.text(),
            "linkedin_url": self._linkedin.text(),
            "github_url": self._github.text(),
            "portfolio": self._portfolio.text(),
        }
        for k, v in fields.items():
            if v:
                data[k] = v

        data["skills"] = self._skills.get_tags()
        data["preferred_locations"] = self._locations.get_tags()
        data["target_companies"] = self._companies.get_tags()
        data["keywords"] = self._keywords.get_tags()

        data["education"] = []
        for i in range(self._edu_list.count()):
            item = self._edu_list.item(i)
            entry = item.data(Qt.ItemDataRole.UserRole)
            if entry:
                data["education"].append(entry)

        data["experience"] = []
        for i in range(self._exp_list.count()):
            item = self._exp_list.item(i)
            entry = item.data(Qt.ItemDataRole.UserRole)
            if entry:
                data["experience"].append(entry)

        return {k: v for k, v in data.items() if v}

    def _clear_form(self) -> None:
        self._display_name.clear()
        self._bio.clear()
        self._avatar_url.clear()
        self._salary.clear()
        self._resume_path.clear()
        self._linkedin.clear()
        self._github.clear()
        self._portfolio.clear()
        self._skills.set_tags([])
        self._locations.set_tags([])
        self._companies.set_tags([])
        self._keywords.set_tags([])
        self._edu_list.clear()
        self._exp_list.clear()
        self._profile_id = None

