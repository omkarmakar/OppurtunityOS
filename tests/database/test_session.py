"""Database session tests."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from database.session import engine, init_db


class TestDatabaseSession:
    """Test suite for database session management."""

    def test_engine_connection(self, tmp_path: Path) -> None:
        """Verify the engine can connect and execute a query.

        The engine URL is resolved from the config singleton, which
        defaults to ``./data/opportunity.db``.  We create that directory
        here so the SQLite engine can write to it.
        """
        data_dir = Path.cwd() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        init_db(data_dir=str(tmp_path / "data"))
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

        # Clean up after ourselves
        import shutil

        shutil.rmtree(data_dir, ignore_errors=True)
