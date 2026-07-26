"""SQLAlchemy database session management."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from core.config import get_config

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def _get_config():
    return get_config()


def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key enforcement on every new SQLite connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine():
    global _engine
    if _engine is None:
        cfg = _get_config()
        _engine = create_engine(
            cfg.database.url,
            echo=cfg.database.echo,
            pool_size=cfg.database.pool_size,
            max_overflow=cfg.database.max_overflow,
            connect_args={"check_same_thread": False},
        )
        if cfg.database.url.startswith("sqlite"):
            event.listen(_engine, "connect", _set_sqlite_pragma)
    return _engine


def get_session_local() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _SessionLocal


SessionLocal = get_session_local()


def __getattr__(name: str):
    if name == "engine":
        return get_engine()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def init_db(data_dir: str | Path | None = None) -> None:
    """Create database directory and initialize tables.

    Args:
        data_dir: Override for the data directory path.
    """
    cfg = _get_config()
    db_path = Path(data_dir or cfg.paths.data_dir)
    db_path.mkdir(parents=True, exist_ok=True)

    # Register all models with Base.metadata before creating tables.
    import database.models  # noqa: F401
    from database.base import Base

    Base.metadata.create_all(bind=get_engine())
