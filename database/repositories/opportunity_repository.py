"""Opportunity repository."""

from __future__ import annotations

from database.models.opportunities import Opportunity
from database.repositories.base import BaseRepository


class OpportunityRepository(BaseRepository[Opportunity]):
    _model = Opportunity
