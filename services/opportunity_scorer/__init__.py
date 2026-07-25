"""Opportunity scoring service — uses AI to score jobs against a user profile."""

from services.opportunity_scorer.scorer import OpportunityScorer, ScoredOpportunity

__all__ = [
    "OpportunityScorer",
    "ScoredOpportunity",
]
