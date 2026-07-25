"""Notification providers for desktop and email delivery."""

from __future__ import annotations

import logging
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage
from typing import Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QSystemTrayIcon

logger = logging.getLogger(__name__)


class BaseNotificationProvider(ABC):
    """Abstract base for notification delivery providers."""

    @abstractmethod
    def send(self, user_id: str, title: str, message: str, **kwargs: Any) -> bool:
        """Deliver a notification. Returns True on success."""


class DesktopNotificationProvider(BaseNotificationProvider):
    """Deliver notifications via the system tray (PySide6)."""

    def __init__(self, tray_icon: QSystemTrayIcon | None = None) -> None:
        self._tray_icon = tray_icon
        if self._tray_icon is None:
            self._init_tray()

    def _init_tray(self) -> None:
        try:
            from PySide6.QtGui import QIcon
            from PySide6.QtWidgets import QApplication, QSystemTrayIcon
            app = QApplication.instance()
            if app and QSystemTrayIcon.isSystemTrayAvailable():
                self._tray_icon = QSystemTrayIcon()
                self._tray_icon.setIcon(QIcon())
                self._tray_icon.show()
            else:
                logger.info("QSystemTrayIcon not available — desktop notifications disabled")
        except Exception as exc:
            logger.debug("Desktop notification init skipped: %s", exc)

    def send(self, user_id: str, title: str, message: str, **kwargs: Any) -> bool:
        if self._tray_icon and self._tray_icon.isVisible():
            try:
                self._tray_icon.showMessage(title, message, timeout=5000)
                return True
            except Exception as exc:
                logger.warning("Desktop notification failed: %s", exc)
        else:
            logger.info("Desktop notification (fallback): [%s] %s — %s", user_id, title, message)
        return False


class EmailNotificationProvider(BaseNotificationProvider):
    """Deliver notifications via SMTP email."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 587,
        username: str = "",
        password: str = "",
        use_tls: bool = True,
        from_address: str = "noreply@opportunityos.local",
        from_name: str = "OpportunityOS",
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._from_address = from_address
        self._from_name = from_name

    def send(self, user_id: str, title: str, message: str, **kwargs: Any) -> bool:
        to = kwargs.get("email_to", "")
        if not to:
            logger.warning("No email_to provided — skipping email notification")
            return False
        try:
            msg = EmailMessage()
            msg.set_content(message)
            msg["Subject"] = title
            msg["From"] = f"{self._from_name} <{self._from_address}>"
            msg["To"] = to
            with smtplib.SMTP(self._host, self._port, timeout=10) as server:
                if self._use_tls:
                    server.starttls()
                if self._username:
                    server.login(self._username, self._password)
                server.send_message(msg)
            logger.info("Email sent to %s: %s", to, title)
            return True
        except Exception as exc:
            logger.error("Email sending failed to %s: %s", to, exc)
            return False
