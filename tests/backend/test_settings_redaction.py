"""Test that credentials are redacted from settings endpoint."""

from __future__ import annotations

from backend.api.v1.endpoints.settings import _redact_db_url


class TestURLRedaction:
    def test_redacts_password(self):
        result = _redact_db_url("postgresql://user:secret@localhost:5432/db")
        assert "secret" not in result
        assert "****" in result
        assert result.startswith("postgresql://user:****@localhost:5432/db")

    def test_no_password_unchanged(self):
        result = _redact_db_url("sqlite:///./data/opportunity.db")
        assert result == "sqlite:///./data/opportunity.db"

    def test_username_only_stays(self):
        result = _redact_db_url("postgresql://user@localhost/db")
        assert "****" not in result

    def test_empty_url(self):
        assert _redact_db_url("") == ""
