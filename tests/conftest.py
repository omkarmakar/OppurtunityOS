"""Pytest fixtures and configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.main import app

# In-memory engine for service-level tests that need a DB session.
_test_engine = create_engine("sqlite://", echo=False, connect_args={"check_same_thread": False})
_test_session_factory: sessionmaker[Session] = sessionmaker(bind=_test_engine)


@pytest.fixture
def db_session() -> Generator:
    """Provide a clean in-memory database session for service tests."""
    from database.base import Base
    import database.models  # noqa: F401

    Base.metadata.create_all(bind=_test_engine)
    session = _test_session_factory()
    try:
        yield session
    finally:
        session.close()
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture
def client() -> Generator:
    """Provide a FastAPI test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
    """Provide a temporary data directory."""
    return tmp_path / "data"
