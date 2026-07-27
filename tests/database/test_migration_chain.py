"""Test the full Alembic migration chain on a fresh SQLite database file."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from alembic.config import Config
from alembic import command

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = PROJECT_ROOT / "database" / "migrations" / "alembic.ini"


class TestMigrationChain:
    """Verify the full migration chain (001->012) runs without error on a fresh SQLite database."""

    def _alembic_cfg(self, db_path: str) -> Config:
        cfg = Config(str(ALEMBIC_INI))
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
        return cfg

    def test_full_chain_upgrade_downgrade(self) -> None:
        """upgrade head → downgrade base → upgrade head, verifying schema at each step."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            cfg = self._alembic_cfg(db_path)

            # ── Step 1: Upgrade all the way to head ──
            command.upgrade(cfg, "head")

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT version_num FROM alembic_version")
            assert cur.fetchone()[0] == "012", "Head revision should be 012"
            conn.close()

            # ── Step 2: Downgrade all the way to base ──
            command.downgrade(cfg, "base")

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM alembic_version")
            assert cur.fetchone()[0] == 0, "Base revision should have no version rows"
            conn.close()

            # ── Step 3: Upgrade again to head (idempotent) ──
            command.upgrade(cfg, "head")

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT version_num FROM alembic_version")
            assert cur.fetchone()[0] == "012", "Head revision should be 012 on re-upgrade"
            conn.close()

            # ── Step 4: Verify migration 010's schema changes ──
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()

            # profiles should NOT have a unique constraint on user_id
            # (no auto-index with origin='u' besides the PK)
            cur.execute("PRAGMA index_list('profiles')")
            for row in cur.fetchall():
                name, origin = row[1], row[3]
                if origin == "u":
                    pytest.fail(f"UNIQUE constraint still present on profiles: {name}")

            # profiles should have non-unique ix_profiles_user_id
            cur.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND tbl_name='profiles' AND name='ix_profiles_user_id'",
            )
            assert cur.fetchone() is not None, "profiles should have ix_profiles_user_id index"

            # profiles should have name column
            cur.execute("PRAGMA table_info('profiles')")
            cols = [r[1] for r in cur.fetchall()]
            assert "name" in cols, "profiles should have name column"

            # profiles should have 011's new columns
            for col in ("raw_extracted_text", "resume_filename", "resume_uploaded_at", "remote_preference"):
                assert col in cols, f"profiles should have '{col}' column from migration 011"

            # opportunities should have profile_id column
            cur.execute("PRAGMA table_info('opportunities')")
            cols = [r[1] for r in cur.fetchall()]
            assert "profile_id" in cols, "opportunities should have profile_id column"

            # ── Step 5: Verify migration 012's schema changes ──
            cur.execute("PRAGMA table_info('scheduler_state')")
            cols = [r[1] for r in cur.fetchall()]
            assert "profile_id" in cols, "scheduler_state should have profile_id column from migration 012"
            assert "user_id" in cols
            assert "task_name" in cols

            conn.close()

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_current_revision_is_012(self) -> None:
        """Sanity check that the head revision is 012 (reminder to update this test)."""
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(self._alembic_cfg(":memory:"))
        heads = script.get_heads()
        assert "012" in heads, f"Expected head revision 012, got {heads}"
