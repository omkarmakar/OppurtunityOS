"""Windows startup registration via HKCU registry."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import winreg
else:
    try:
        import winreg
    except ImportError:
        winreg = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

APP_NAME = "OpportunityOS"


def _get_command() -> str:
    """Return the command line to register for Windows startup."""
    return f'"{sys.executable}" -m frontend.main'


def is_registered() -> bool:
    """Check if the app is registered for Windows startup."""
    if winreg is None:
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ,
        )
        value, _ = winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return value == _get_command()
    except OSError:
        return False


def register() -> bool:
    """Register the app to launch on Windows startup. Returns True on success."""
    if winreg is None:
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _get_command())
        winreg.CloseKey(key)
        logger.info("Registered for Windows startup")
        return True
    except OSError as exc:
        logger.debug("Failed to register Windows startup: %s", exc)
        return False


def unregister() -> bool:
    """Remove the Windows startup registration. Returns True on success."""
    if winreg is None:
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
        logger.info("Removed Windows startup registration")
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        logger.debug("Failed to remove Windows startup registration: %s", exc)
        return False
