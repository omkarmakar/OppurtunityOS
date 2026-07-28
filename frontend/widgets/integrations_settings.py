"""Settings UI for API integrations and behavior toggles."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QVBoxLayout, QWidget, QComboBox,
)

from frontend.theme import (
    ACCENT, ACCENT_HOVER, BG_CARD, BG_INPUT, BG_INPUT_HOVER,
    BORDER_DEFAULT, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    FONT_FAMILY, RADIUS_MD,
)


class IntegrationRow(QWidget):
    """Single integration API key editor with test button."""

    test_requested = Signal(str, str)  # (key_name, key_value)
    key_changed = Signal(str, str)  # (key_name, key_value)

    def __init__(
        self,
        key_name: str,
        display_name: str,
        current_value: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._key_name = key_name
        self._display_name = display_name
        self._setup_ui(current_value or "")

    def _setup_ui(self, current_value: str) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Label
        label = QLabel(self._display_name)
        label.setFixedWidth(180)
        label.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: 500;
                color: {TEXT_PRIMARY};
                background: transparent;
            }}
        """)
        layout.addWidget(label)

        # Input field
        self._input = QLineEdit()
        self._input.setText(current_value)
        self._input.setEchoMode(QLineEdit.EchoMode.Password)
        self._input.setPlaceholderText("Enter API key...")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {BG_INPUT};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
                color: {TEXT_PRIMARY};
                padding: 8px 12px;
                font-family: {FONT_FAMILY};
                font-size: 12px;
            }}
            QLineEdit:hover {{
                background-color: {BG_INPUT_HOVER};
            }}
            QLineEdit:focus {{
                border: 1px solid {ACCENT};
                background-color: {BG_INPUT};
            }}
        """)
        self._input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._input, 1)

        # Test button
        self._test_btn = QPushButton("Test")
        self._test_btn.setFixedWidth(80)
        self._test_btn.clicked.connect(self._on_test_clicked)
        self._test_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 500;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                opacity: 0.8;
            }}
        """)
        layout.addWidget(self._test_btn)

    def _on_text_changed(self) -> None:
        """Emit key_changed signal."""
        self.key_changed.emit(self._key_name, self._input.text())

    def _on_test_clicked(self) -> None:
        """Emit test_requested signal."""
        self.test_requested.emit(self._key_name, self._input.text())

    def get_value(self) -> str:
        """Get current API key value."""
        return self._input.text()

    def set_value(self, value: str) -> None:
        """Set API key value."""
        self._input.setText(value)


class BehaviorToggle(QWidget):
    """Checkbox toggle for behavior settings."""

    toggled = Signal(str, bool)  # (setting_name, value)

    def __init__(
        self,
        setting_name: str,
        display_name: str,
        description: str = "",
        checked: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._setting_name = setting_name
        self._setup_ui(display_name, description, checked)

    def _setup_ui(self, display_name: str, description: str, checked: bool) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        # Checkbox + label
        top_layout = QHBoxLayout()
        self._checkbox = QCheckBox()
        self._checkbox.setChecked(checked)
        self._checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {TEXT_PRIMARY};
                spacing: 8px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid {BORDER_DEFAULT};
                background-color: {BG_INPUT};
            }}
            QCheckBox::indicator:checked {{
                background-color: {ACCENT};
                border: 1px solid {ACCENT};
            }}
        """)
        self._checkbox.stateChanged.connect(self._on_toggled)
        top_layout.addWidget(self._checkbox, 0, Qt.AlignmentFlag.AlignLeft)

        label = QLabel(display_name)
        label.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: 500;
                color: {TEXT_PRIMARY};
                background: transparent;
            }}
        """)
        top_layout.addWidget(label, 0, Qt.AlignmentFlag.AlignLeft)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Description
        if description:
            desc = QLabel(description)
            desc.setWordWrap(True)
            desc.setStyleSheet(f"""
                QLabel {{
                    font-size: 11px;
                    color: {TEXT_MUTED};
                    background: transparent;
                    margin-top: -4px;
                }}
            """)
            layout.addWidget(desc)

    def _on_toggled(self) -> None:
        """Emit toggled signal."""
        self.toggled.emit(self._setting_name, self._checkbox.isChecked())

    def is_checked(self) -> bool:
        """Get checkbox state."""
        return self._checkbox.isChecked()

    def set_checked(self, checked: bool) -> None:
        """Set checkbox state."""
        self._checkbox.setChecked(checked)


class IntegrationDropdown(QWidget):
    """Dropdown selector for integration choices."""

    selection_changed = Signal(str, str)  # (setting_name, value)

    def __init__(
        self,
        setting_name: str,
        display_name: str,
        options: list[str],
        current_value: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._setting_name = setting_name
        self._setup_ui(display_name, options, current_value)

    def _setup_ui(self, display_name: str, options: list[str], current_value: str) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Label
        label = QLabel(display_name)
        label.setFixedWidth(180)
        label.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: 500;
                color: {TEXT_PRIMARY};
                background: transparent;
            }}
        """)
        layout.addWidget(label)

        # Dropdown
        self._combo = QComboBox()
        self._combo.addItems(options)
        if current_value in options:
            self._combo.setCurrentText(current_value)
        self._combo.currentTextChanged.connect(self._on_selection_changed)
        self._combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {BG_INPUT};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
                padding: 6px 10px;
                font-size: 12px;
            }}
            QComboBox:hover {{
                background-color: {BG_INPUT_HOVER};
            }}
            QComboBox::drop-down {{
                border: none;
                background: transparent;
            }}
            QComboBox QAbstractItemView {{
                background-color: {BG_CARD};
                color: {TEXT_PRIMARY};
                selection-background-color: {ACCENT};
            }}
        """)
        layout.addWidget(self._combo, 1)

    def _on_selection_changed(self) -> None:
        """Emit selection_changed signal."""
        self.selection_changed.emit(self._setting_name, self._combo.currentText())

    def get_value(self) -> str:
        """Get selected value."""
        return self._combo.currentText()

    def set_value(self, value: str) -> None:
        """Set selected value."""
        if value in [self._combo.itemText(i) for i in range(self._combo.count())]:
            self._combo.setCurrentText(value)
