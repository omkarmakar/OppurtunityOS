"""Custom exception classes for OpportunityOS."""

from __future__ import annotations


class OpportunityOSError(Exception):
    """Base exception for all application errors."""


class ConfigurationError(OpportunityOSError):
    """Raised when application configuration is invalid or missing."""


class DatabaseError(OpportunityOSError):
    """Raised when a database operation fails."""


class ServiceError(OpportunityOSError):
    """Raised when a service operation fails."""


class PluginError(OpportunityOSError):
    """Raised when a plugin operation fails."""
