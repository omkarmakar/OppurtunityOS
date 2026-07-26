"""Multi-profile management page with switcher, create/edit/delete."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
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
    RED,
    TEXT_BRIGHT,
    TEXT_MUTED,
    TEXT_SECONDARY,
    card_frame_stylesheet,
)
from frontend.user_context import get_active_user_id
from frontend.widgets.profile_form import ProfileForm

API_BASE = "http://127.0.0.1:8000/api/v1"
MAX_PROFILES = 5


class ProfileCard(QFrame):
    """A clickable card in the profile switcher strip."""

    def __init__(
        self,
        profile_data: dict[str, Any],
        active: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._data = profile_data
        self._profile_id = profile_data.get("id", "")
        self.setObjectName("profileCard")
        border_left = ACCENT if active else "transparent"
        self.setStyleSheet(card_frame_stylesheet("profileCard", border_left=border_left) + """
            QFrame#profileCard:hover {
                border: 1px solid """ + ACCENT_LIGHT + """;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(180)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Header row: name + delete
        header_row = QHBoxLayout()
        header_row.setSpacing(4)
        name_label = QLabel(profile_data.get("name", "Untitled"))
        name_label.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {TEXT_BRIGHT}; background: transparent;")
        header_row.addWidget(name_label, 1)

        delete_btn = QPushButton("\u2716")
        delete_btn.setFixedSize(22, 22)
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {RED}; border: none;
                font-size: 14px; font-weight: bold;
            }}
            QPushButton:hover {{ background: #3a1a1a; border-radius: 4px; }}
        """)
        delete_btn.clicked.connect(self._delete_clicked)
        header_row.addWidget(delete_btn)
        layout.addLayout(header_row)

        # Subtitle: first line of bio, top skill, or role
        subtitle = self._derive_subtitle(profile_data)
        sub_label = QLabel(subtitle)
        sub_label.setWordWrap(True)
        sub_label.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;")
        layout.addWidget(sub_label)

    def _derive_subtitle(self, data: dict[str, Any]) -> str:
        bio = data.get("bio", "").strip()
        if bio:
            return bio.split("\n")[0][:60]
        skills = data.get("skills") or []
        if skills:
            return skills[0][:60]
        locations = data.get("preferred_locations") or []
        if locations:
            return locations[0][:60]
        return "No details yet"

    def _delete_clicked(self) -> None:
        parent = self.window() if self.window() else self
        confirm = QMessageBox.question(
            parent, "Delete Profile",
            f'Delete "{self._data.get("name", "this profile")}"?\nThis cannot be undone.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                resp = httpx.delete(f"{API_BASE}/profiles/id/{self._profile_id}", timeout=10)
                if resp.status_code == 204:
                    parent_widget = self.parentWidget()
                    while parent_widget and not hasattr(parent_widget, "_on_profile_deleted"):
                        parent_widget = parent_widget.parentWidget()
                    if parent_widget:
                        parent_widget._on_profile_deleted(self._profile_id)  # type: ignore[union-attr]
                elif resp.status_code == 409:
                    QMessageBox.warning(parent, "Cannot Delete", resp.json().get("detail", "Cannot delete last profile."))
            except httpx.HTTPError as e:
                QMessageBox.critical(parent, "Error", f"Failed to delete:\n{e}")

    def mousePressEvent(self, event) -> None:
        parent_widget = self.parentWidget()
        while parent_widget and not hasattr(parent_widget, "_on_profile_selected"):
            parent_widget = parent_widget.parentWidget()
        if parent_widget:
            parent_widget._on_profile_selected(self._profile_id)  # type: ignore[union-attr]
        super().mousePressEvent(event)

    def profile_id(self) -> str:
        return self._profile_id


class NewProfileCard(QFrame):
    """The '+ New Profile' card at the end of the switcher strip."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("newProfileCard")
        self.setStyleSheet(f"""
            QFrame#newProfileCard {{
                background-color: {BG_ELEVATED};
                border: 2px dashed {BORDER_SUBTLE};
                border-radius: 10px;
            }}
            QFrame#newProfileCard:hover {{
                border-color: {ACCENT_LIGHT};
                background-color: {ACCENT_MUTED_BG};
            }}
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(180)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel("+ New Profile")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {ACCENT_LIGHT}; background: transparent;")
        layout.addWidget(label)
        hint = QLabel("Create a new profile")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;")
        layout.addWidget(hint)

    def set_disabled(self, disabled: bool) -> None:
        self.setEnabled(not disabled)
        if disabled:
            self.setToolTip(f"Maximum of {MAX_PROFILES} profiles reached.")
            self.setStyleSheet(f"""
                QFrame#newProfileCard {{
                    background-color: {BG_CARD};
                    border: 2px dashed {BORDER_SUBTLE};
                    border-radius: 10px;
                    opacity: 0.5;
                }}
            """)
        else:
            self.setToolTip("")
            self.setStyleSheet(f"""
                QFrame#newProfileCard {{
                    background-color: {BG_ELEVATED};
                    border: 2px dashed {BORDER_SUBTLE};
                    border-radius: 10px;
                }}
                QFrame#newProfileCard:hover {{
                    border-color: {ACCENT_LIGHT};
                    background-color: {ACCENT_MUTED_BG};
                }}
            """)

    def mousePressEvent(self, event) -> None:
        if not self.isEnabled():
            return
        parent_widget = self.parentWidget()
        while parent_widget and not hasattr(parent_widget, "_on_new_profile"):
            parent_widget = parent_widget.parentWidget()
        if parent_widget:
            parent_widget._on_new_profile()  # type: ignore[union-attr]
        super().mousePressEvent(event)


class ProfilePage(PageWidget):
    """Multi-profile management page."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self._profiles: list[dict[str, Any]] = []
        self._active_profile_id: str | None = None
        self._profile_form: ProfileForm | None = None
        self._switcher_widget: QWidget | None = None
        self._empty_widget: QWidget | None = None
        self._form_container: QWidget | None = None
        self._switcher_scroll: QScrollArea | None = None
        super().__init__("Profile", parent)

    def _setup_ui(self) -> None:
        # Override PageWidget._setup_ui with our own layout
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

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("QFrame { color: #2a2a44; max-height: 1px; }")
        layout.addWidget(separator)
        layout.addSpacing(16)

        # Profile switcher strip
        self._switcher_widget = QWidget()
        self._switcher_widget.setStyleSheet("background: transparent;")
        self._switcher_widget.setVisible(False)
        layout.addWidget(self._switcher_widget)

        # Empty state (shown when 0 profiles)
        self._empty_widget = QWidget()
        self._empty_widget.setStyleSheet("background: transparent;")
        self._empty_widget.setVisible(False)
        layout.addWidget(self._empty_widget, 1)

        # Form container (shown when a profile is selected or being created)
        self._form_container = QWidget()
        self._form_container.setStyleSheet("background: transparent;")
        self._form_container.setVisible(False)
        layout.addWidget(self._form_container, 1)

        self._build_switcher()
        self._build_empty_state()
        self._build_form_container()

        # Load profiles on init
        self._fetch_profiles()

    def _build_switcher(self) -> None:
        # The switcher is rebuilt each time profiles change
        pass

    def _rebuild_switcher(self) -> None:
        if not self._switcher_widget:
            return
        # Clear old content
        for child in self._switcher_widget.findChildren(QWidget, "", Qt.FindChildOption.FindChildrenRecursively):
            child.deleteLater()

        layout = QVBoxLayout(self._switcher_widget)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(8)

        label = QLabel("Your Profiles")
        label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {TEXT_SECONDARY}; background: transparent;")
        layout.addWidget(label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(130)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(inner)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)

        for profile in self._profiles:
            card = ProfileCard(
                profile,
                active=profile.get("id") == self._active_profile_id,
            )
            row_layout.addWidget(card)

        self._new_profile_card = NewProfileCard()
        self._new_profile_card.set_disabled(len(self._profiles) >= MAX_PROFILES)
        row_layout.addWidget(self._new_profile_card)

        row_layout.addStretch(1)
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        self._switcher_widget.setVisible(True)

    def _on_new_profile_card_click(self, event) -> None:
        if len(self._profiles) >= MAX_PROFILES:
            QMessageBox.information(
                self, "Limit Reached",
                f"You can have at most {MAX_PROFILES} profiles.",
            )
            return
        self._on_new_profile()

    # ── empty state ────────────────────────────────────────────────────

    def _build_empty_state(self) -> None:
        if not self._empty_widget:
            return
        for child in self._empty_widget.findChildren(QWidget, "", Qt.FindChildOption.FindChildrenRecursively):
            child.deleteLater()

        layout = QVBoxLayout(self._empty_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        title = QLabel("Create Your First Profile")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {TEXT_BRIGHT}; background: transparent;")
        layout.addWidget(title)

        desc = QLabel(
            "A profile helps us find the best opportunities for you.\n"
            "You can create up to 5 profiles for different job search tracks."
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

        btn_row.addWidget(upload_btn)
        btn_row.addWidget(manual_btn)
        layout.addLayout(btn_row)

    # ── form container ─────────────────────────────────────────────────

    def _build_form_container(self) -> None:
        if not self._form_container:
            return
        for child in self._form_container.findChildren(QWidget, "", Qt.FindChildOption.FindChildrenRecursively):
            child.deleteLater()

        layout = QVBoxLayout(self._form_container)
        layout.setContentsMargins(0, 0, 0, 0)
        self._profile_form = ProfileForm(on_saved=self._on_profile_saved)
        layout.addWidget(self._profile_form, 1)

    # ── API calls ───────────────────────────────────────────────────────

    def _fetch_profiles(self) -> None:
        uid = get_active_user_id()
        try:
            resp = httpx.get(f"{API_BASE}/users/{uid}/profiles", timeout=10)
            resp.raise_for_status()
            self._profiles = resp.json()
        except httpx.HTTPError:
            self._profiles = []

        self._sync_ui()

    def _sync_ui(self) -> None:
        if not self._profiles:
            self._switcher_widget.setVisible(False)
            self._form_container.setVisible(False)
            self._build_empty_state()
            self._empty_widget.setVisible(True)
        else:
            self._empty_widget.setVisible(False)
            self._rebuild_switcher()
            self._switcher_widget.setVisible(True)

            # If no active profile, select the first one
            if not self._active_profile_id or self._active_profile_id not in {p.get("id") for p in self._profiles}:
                self._active_profile_id = self._profiles[0].get("id")

            # Show form for active profile
            self._load_profile_into_form(self._active_profile_id)
            self._form_container.setVisible(True)

    def _load_profile_into_form(self, profile_id: str | None) -> None:
        if not profile_id or not self._profile_form:
            return
        try:
            resp = httpx.get(f"{API_BASE}/profiles/id/{profile_id}", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            self._profile_form.clear()
            self._profile_form.set_profile_id(profile_id)
            self._profile_form.populate(data)
        except httpx.HTTPError:
            QMessageBox.warning(self, "Error", "Failed to load profile data.")

    # ── callbacks ──────────────────────────────────────────────────────

    def _on_profile_selected(self, profile_id: str) -> None:
        if profile_id == self._active_profile_id:
            return
        self._active_profile_id = profile_id
        # Rebuild switcher to highlight active card
        self._rebuild_switcher()
        self._load_profile_into_form(profile_id)

    def _on_profile_deleted(self, profile_id: str) -> None:
        self._profiles = [p for p in self._profiles if p.get("id") != profile_id]
        if self._active_profile_id == profile_id:
            self._active_profile_id = None
        self._sync_ui()

    def _on_new_profile(self) -> None:
        """Show the Upload vs Manual choice."""
        choice = QWidget(None, Qt.WindowType.Dialog)
        choice.setWindowTitle("New Profile")
        choice.setMinimumWidth(480)
        choice.setStyleSheet("""
            QWidget { background-color: #12121f; color: #e4e4f0; }
        """)
        layout = QVBoxLayout(choice)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("How would you like to create this profile?")
        title.setWordWrap(True)
        title.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #f0f0ff; background: transparent;"
        )
        layout.addWidget(title)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)

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
        upload_btn.clicked.connect(lambda: self._on_upload_resume_dialog(choice))
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
        manual_btn.clicked.connect(lambda: self._on_fill_manual_dialog(choice))
        btn_row.addWidget(manual_btn)

        layout.addLayout(btn_row)
        layout.addStretch(1)
        choice.setLayout(layout)
        choice.exec()

    def _on_upload_resume_dialog(self, dialog: QWidget) -> None:
        dialog.close()
        self._on_upload_resume()

    def _on_fill_manual_dialog(self, dialog: QWidget) -> None:
        dialog.close()
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
        except httpx.HTTPError as e:
            QMessageBox.critical(self, "Error", f"Parse failed:\n{e}")
            return

        # Build a partial profile dict from parsed data
        partial: dict[str, Any] = {}
        if data.get("skills"):
            partial["skills"] = data["skills"]
        if data.get("education"):
            partial["education"] = data["education"]
        if data.get("experience"):
            partial["experience"] = data["experience"]
        if data.get("projects"):
            partial["projects"] = data["projects"]

        # Derive a suggested name from parsed data
        name_suggestion = self._derive_name_from_parsed(data)

        # Show the form with parsed data pre-filled, in create mode
        self._show_create_form(partial, name_suggestion)

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
        """Show the ProfileForm in create mode with optional pre-filled data."""
        self._empty_widget.setVisible(False)
        self._switcher_widget.setVisible(False)

        self._build_form_container()
        if self._profile_form:
            self._profile_form.set_name_suggestion(name_suggestion or None)
            self._profile_form.populate(prefill)
            self._profile_form.set_profile_id(None)

        self._form_container.setVisible(True)

    def _on_profile_saved(self, profile_id: str | None) -> None:
        """Callback after a profile is saved — refresh list and select it."""
        self._active_profile_id = profile_id
        self._fetch_profiles()
