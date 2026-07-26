"""Reusable profile form widget — create and edit profiles."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


from frontend.user_context import get_active_user_id

API_BASE = "http://127.0.0.1:8000/api/v1"


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
        self._input.returnPressed.connect(self._add_tag)
        add_btn = QPushButton("+")
        add_btn.setFixedWidth(32)
        add_btn.clicked.connect(self._add_tag)
        input_row.addWidget(self._input, 1)
        input_row.addWidget(add_btn)
        layout.addLayout(input_row)

        self._list = QListWidget()
        self._list.setMaximumHeight(120)
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


class FormSection(QGroupBox):
    """A styled section for profile form fields."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)


class ProfileForm(QWidget):
    """Reusable form for creating/editing a profile.

    Modes:
      - create: POST /profiles on save (no profile_id set)
      - edit: PUT /profiles/id/{profile_id} on save
      - review: pre-filled with parsed resume data, user edits then saves (create mode)
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        on_saved: callable | None = None,
    ) -> None:
        super().__init__(parent)
        self._profile_id: str | None = None
        self._user_id: str = get_active_user_id()
        self._profile_name_suggestion: str | None = None
        self._on_saved = on_saved
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setStyleSheet("QWidget { background: transparent; }")
        form_layout = QVBoxLayout(content)
        form_layout.setSpacing(8)
        form_layout.setContentsMargins(0, 0, 0, 0)

        self._build_name_row(form_layout)
        self._build_basic_info(form_layout)
        self._build_education(form_layout)
        self._build_experience(form_layout)
        self._build_projects(form_layout)
        self._build_skills(form_layout)
        self._build_locations(form_layout)
        self._build_companies(form_layout)
        self._build_keywords(form_layout)
        self._build_salary(form_layout)
        self._build_links(form_layout)
        self._build_buttons(form_layout)

        form_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

    # ── helpers ─────────────────────────────────────────────────────────

    def _line_edit(self, placeholder: str = "") -> QLineEdit:
        le = QLineEdit()
        le.setPlaceholderText(placeholder)
        return le

    def _text_edit(self) -> QTextEdit:
        te = QTextEdit()
        te.setMaximumHeight(100)
        return te

    # ── build sections ──────────────────────────────────────────────────

    def _build_name_row(self, parent_layout: QVBoxLayout) -> None:
        section = FormSection("Profile Label")
        form = QFormLayout(section)
        form.setSpacing(8)
        self._name = self._line_edit("e.g. R&D Track, AI/ML Track")
        form.addRow("Name:", self._name)
        parent_layout.addWidget(section)

    def _build_basic_info(self, parent_layout: QVBoxLayout) -> None:
        section = FormSection("Basic Information")
        form = QFormLayout(section)
        form.setSpacing(8)
        self._display_name = self._line_edit("Display name")
        form.addRow("Display Name:", self._display_name)
        self._bio = self._text_edit()
        form.addRow("Bio:", self._bio)
        parent_layout.addWidget(section)

    def _build_education(self, parent_layout: QVBoxLayout) -> None:
        section = FormSection("Education")
        layout = QVBoxLayout(section)
        self._edu_list = QListWidget()
        layout.addWidget(self._edu_list)
        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Education")
        add_btn.clicked.connect(self._add_education)
        rm_btn = QPushButton("Remove Selected")
        rm_btn.clicked.connect(lambda: self._remove_list_item(self._edu_list))
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        parent_layout.addWidget(section)

    def _build_experience(self, parent_layout: QVBoxLayout) -> None:
        section = FormSection("Experience")
        layout = QVBoxLayout(section)
        self._exp_list = QListWidget()
        layout.addWidget(self._exp_list)
        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Experience")
        add_btn.clicked.connect(self._add_experience)
        rm_btn = QPushButton("Remove Selected")
        rm_btn.clicked.connect(lambda: self._remove_list_item(self._exp_list))
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        parent_layout.addWidget(section)

    def _build_projects(self, parent_layout: QVBoxLayout) -> None:
        section = FormSection("Projects")
        layout = QVBoxLayout(section)
        self._proj_list = QListWidget()
        layout.addWidget(self._proj_list)
        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Project")
        add_btn.clicked.connect(self._add_project)
        rm_btn = QPushButton("Remove Selected")
        rm_btn.clicked.connect(lambda: self._remove_list_item(self._proj_list))
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        parent_layout.addWidget(section)

    def _build_skills(self, parent_layout: QVBoxLayout) -> None:
        section = FormSection("Skills")
        layout = QVBoxLayout(section)
        self._skills = TagInput()
        layout.addWidget(self._skills)
        parent_layout.addWidget(section)

    def _build_locations(self, parent_layout: QVBoxLayout) -> None:
        section = FormSection("Preferred Locations")
        layout = QVBoxLayout(section)
        self._locations = TagInput()
        layout.addWidget(self._locations)
        parent_layout.addWidget(section)

    def _build_companies(self, parent_layout: QVBoxLayout) -> None:
        section = FormSection("Target Companies")
        layout = QVBoxLayout(section)
        self._companies = TagInput()
        layout.addWidget(self._companies)
        parent_layout.addWidget(section)

    def _build_keywords(self, parent_layout: QVBoxLayout) -> None:
        section = FormSection("Keywords")
        layout = QVBoxLayout(section)
        self._keywords = TagInput()
        layout.addWidget(self._keywords)
        parent_layout.addWidget(section)

    def _build_salary(self, parent_layout: QVBoxLayout) -> None:
        section = FormSection("Salary Expectations")
        layout = QVBoxLayout(section)
        self._salary = self._line_edit("e.g. 120k-150k")
        layout.addWidget(self._salary)
        parent_layout.addWidget(section)

    def _build_links(self, parent_layout: QVBoxLayout) -> None:
        section = FormSection("Links")
        form = QFormLayout(section)
        form.setSpacing(8)
        self._linkedin = self._line_edit("https://linkedin.com/in/...")
        form.addRow("LinkedIn:", self._linkedin)
        self._github = self._line_edit("https://github.com/...")
        form.addRow("GitHub:", self._github)
        self._portfolio = self._line_edit("https://...")
        form.addRow("Portfolio:", self._portfolio)
        parent_layout.addWidget(section)

    def _build_buttons(self, parent_layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 16, 0, 0)
        row.setSpacing(12)
        self._save_btn = QPushButton("Save Profile")
        self._save_btn.clicked.connect(self._save)
        row.addStretch(1)
        row.addWidget(self._save_btn)
        parent_layout.addLayout(row)

    # ── dialogs ─────────────────────────────────────────────────────────

    def _show_entry_dialog(
        self, title: str, fields: list[tuple[str, str]],
    ) -> dict[str, str] | None:
        dialog = QWidget(None, Qt.WindowType.Dialog)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(400)
        dialog.setStyleSheet("""
            QWidget { background-color: #1a1a2e; color: #e4e4f0; font-size: 13px; }
            QLineEdit {
                padding: 6px 10px; border: 1px solid #2a2a44;
                border-radius: 6px; background-color: #0f0f1a; color: #e4e4f0;
            }
            QLineEdit:focus { border-color: #7c3aed; }
            QPushButton {
                padding: 6px 16px; border: none; border-radius: 6px;
                font-weight: 600; color: #e4e4f0;
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

    def _add_project(self) -> None:
        result = self._show_entry_dialog("Add Project", [
            ("Name", "My App"),
            ("Description", "What it does"),
            ("Technologies", "Python, FastAPI"),
            ("URL", "https://github.com/user/app"),
        ])
        if result and result.get("Name"):
            text = f"[Project] {result['Name']} - {result['Technologies']}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, result)
            self._proj_list.addItem(item)

    def _remove_list_item(self, lst: QListWidget) -> None:
        for item in lst.selectedItems():
            lst.takeItem(lst.row(item))

    # ── data population / collection ────────────────────────────────────

    def set_profile_id(self, profile_id: str | None) -> None:
        self._profile_id = profile_id

    def get_profile_id(self) -> str | None:
        return self._profile_id

    def set_user_id(self, user_id: str) -> None:
        self._user_id = user_id

    def set_name_suggestion(self, name: str | None) -> None:
        self._profile_name_suggestion = name
        if name and not self._name.text():
            self._name.setText(name)

    def populate(self, data: dict[str, Any]) -> None:
        self._name.setText(data.get("name") or "")
        self._display_name.setText(data.get("display_name") or "")
        self._bio.setPlainText(data.get("bio") or "")
        self._salary.setText(data.get("salary_expectations") or "")
        self._linkedin.setText(data.get("linkedin_url") or "")
        self._github.setText(data.get("github_url") or "")
        self._portfolio.setText(data.get("portfolio") or "")

        self._skills.set_tags(data.get("skills") or [])
        self._locations.set_tags(data.get("preferred_locations") or [])
        self._companies.set_tags(data.get("target_companies") or [])
        self._keywords.set_tags(data.get("keywords") or [])

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

        self._proj_list.clear()
        for entry in data.get("projects") or []:
            text = f"[Project] {entry.get('name','')} - {entry.get('technologies','')}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._proj_list.addItem(item)

    def collect(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        fields = {
            "display_name": self._display_name.text(),
            "bio": self._bio.toPlainText(),
            "salary_expectations": self._salary.text(),
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

        data["projects"] = []
        for i in range(self._proj_list.count()):
            item = self._proj_list.item(i)
            entry = item.data(Qt.ItemDataRole.UserRole)
            if entry:
                data["projects"].append(entry)

        result = {k: v for k, v in data.items() if v}
        name = self._name.text().strip()
        if name:
            result["name"] = name
        return result

    def clear(self) -> None:
        self._name.clear()
        self._display_name.clear()
        self._bio.clear()
        self._salary.clear()
        self._linkedin.clear()
        self._github.clear()
        self._portfolio.clear()
        self._skills.set_tags([])
        self._locations.set_tags([])
        self._companies.set_tags([])
        self._keywords.set_tags([])
        self._edu_list.clear()
        self._exp_list.clear()
        self._proj_list.clear()
        self._profile_id = None

    # ── save ────────────────────────────────────────────────────────────

    def _save(self) -> None:
        import httpx

        data = self.collect()
        data["name"] = self._name.text().strip() or f"Profile {self._profile_id or 'New'}"
        try:
            if self._profile_id:
                resp = httpx.put(
                    f"{API_BASE}/profiles/id/{self._profile_id}",
                    json=data, timeout=10,
                )
                resp.raise_for_status()
                QMessageBox.information(self, "Saved", "Profile updated.")
                self.populate(resp.json())
            else:
                data["user_id"] = self._user_id
                resp = httpx.post(
                    f"{API_BASE}/profiles",
                    json=data, timeout=10,
                )
                resp.raise_for_status()
                saved = resp.json()
                self._profile_id = saved.get("id")
                QMessageBox.information(self, "Created", "Profile created.")
                self.populate(saved)
        except httpx.HTTPError as e:
            QMessageBox.critical(self, "Error", f"Failed to save profile:\n{e}")
            return
        if self._on_saved:
            self._on_saved(self._profile_id)
