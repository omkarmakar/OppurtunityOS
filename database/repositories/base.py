"""Generic repository base class."""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from database.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Abstract data-access base for a single ORM model.

    Usage::

        class UserRepository(BaseRepository[User]):
            _model = User

        repo = UserRepository(session)
        user = repo.get(some_uuid)
    """

    _model: type[ModelT]

    def __init__(self, session: Session) -> None:
        """Initialize the repository.

        Args:
            session: Active SQLAlchemy ORM session.
        """
        self._session = session

    # ── standard operations ───────────────────────────────────────────

    def get(self, id: Any) -> Optional[ModelT]:
        """Retrieve an entity by its primary key.

        Args:
            id: Primary key value.

        Returns:
            The matching entity, or ``None`` if not found.
        """
        return self._session.get(self._model, id)

    def list(self, **filters: Any) -> list[ModelT]:
        """Return all entities matching the given keyword filters.

        Each filter is applied as ``column == value``.
        Pass no arguments to retrieve every row.

        Args:
            **filters: Column-value pairs to filter by.

        Returns:
            List of matching entities.
        """
        stmt = select(self._model)
        if filters:
            for column, value in filters.items():
                col_attr = getattr(self._model, column, None)
                if col_attr is not None:
                    stmt = stmt.where(col_attr == value)
        return list(self._session.scalars(stmt).all())

    def add(self, entity: ModelT) -> ModelT:
        """Persist a new entity (flush, no commit).

        Args:
            entity: Transient ORM instance.

        Returns:
            The same instance with its primary key populated.
        """
        self._session.add(entity)
        self._session.flush()
        return entity

    def update(self, entity: ModelT) -> ModelT:
        """Mark a dirty entity for flush.

        Args:
            entity: Previously-persisted ORM instance.

        Returns:
            The same instance.
        """
        self._session.add(entity)
        self._session.flush()
        return entity

    def delete(self, entity: ModelT) -> None:
        """Delete an entity.

        Args:
            entity: Persisted ORM instance to remove.
        """
        self._session.delete(entity)
        self._session.flush()

    def count(self, **filters: Any) -> int:
        """Return the number of rows matching the given filters.

        Args:
            **filters: Column-value pairs to filter by.

        Returns:
            Row count.
        """
        stmt = select(func.count()).select_from(self._model)
        if filters:
            for column, value in filters.items():
                col_attr = getattr(self._model, column, None)
                if col_attr is not None:
                    stmt = stmt.where(col_attr == value)
        result = self._session.execute(stmt)
        return result.scalar_one()

    def exists(self, id: Any) -> bool:
        """Check whether an entity with the given primary key exists.

        Args:
            id: Primary key value.

        Returns:
            ``True`` if the row exists.
        """
        return self._session.get(self._model, id) is not None
