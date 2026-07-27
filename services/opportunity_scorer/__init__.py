"""Opportunity scoring service — uses AI or embeddings to score jobs against a user profile."""

from services.opportunity_scorer.embedding_scorer import (
    EmbeddingOpportunityScorer,
    create_opportunity_scorer,
)
from services.opportunity_scorer.scorer import OpportunityScorer, ScoredOpportunity

__all__ = [
    "EmbeddingOpportunityScorer",
    "OpportunityScorer",
    "ScoredOpportunity",
    "create_opportunity_scorer",
]
