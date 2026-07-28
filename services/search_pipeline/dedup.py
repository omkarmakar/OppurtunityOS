"""Opportunity deduplication utilities using fuzzy matching.

Implements two-stage deduplication:
1. Exact URL match (fast)
2. Fuzzy match on (company, title) across job boards (catches duplicates from multiple sources)
"""

from __future__ import annotations

import difflib
from typing import Optional

from database.models.opportunities import Opportunity


def normalize_text(text: Optional[str]) -> str:
    """Normalize text for fuzzy matching.

    - Lowercase
    - Strip punctuation and extra spaces
    - Remove common job board prefixes

    Args:
        text: Text to normalize

    Returns:
        Normalized text
    """
    if not text:
        return ""
    
    text = text.lower().strip()
    # Remove common job board terms and prefixes
    prefixes = ["senior", "junior", "lead", "principal", "staff", "sr.", "jr."]
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    
    return text


def token_set_similarity(s1: str, s2: str, threshold: float = 0.85) -> tuple[float, bool]:
    """Calculate token-set similarity between two strings.

    Uses sequence matching with normalized tokens. Returns similarity score
    and boolean indicating if it exceeds threshold.

    Args:
        s1: First string
        s2: Second string
        threshold: Similarity threshold (0-1)

    Returns:
        Tuple of (similarity_score, exceeds_threshold)
    """
    norm1 = normalize_text(s1)
    norm2 = normalize_text(s2)
    
    if not norm1 or not norm2:
        return (1.0 if norm1 == norm2 else 0.0, norm1 == norm2)
    
    # Use SequenceMatcher for fuzzy matching
    matcher = difflib.SequenceMatcher(None, norm1, norm2)
    ratio = matcher.ratio()
    
    return (ratio, ratio >= threshold)


def company_title_key(opportunity: Opportunity) -> tuple[Optional[str], str]:
    """Extract (company, title) key for fuzzy dedup matching.

    Args:
        opportunity: Opportunity record

    Returns:
        Tuple of (company, normalized_title)
    """
    company = (opportunity.company or "unknown").lower().strip() if opportunity.company else "unknown"
    title = normalize_text(opportunity.title)
    return (company, title)


def is_duplicate_by_company_title(
    opportunity: Opportunity,
    existing_opportunities: list[Opportunity],
    similarity_threshold: float = 0.85,
) -> bool:
    """Check if opportunity is a duplicate of any in the existing list using fuzzy matching.

    Only considers opportunities from the same user and profile, matching on
    (company, title) tuple with token-set similarity.

    Args:
        opportunity: Opportunity to check
        existing_opportunities: List of opportunities to check against (same user/profile)
        similarity_threshold: Similarity threshold for matching (0-1)

    Returns:
        True if a duplicate is found, False otherwise
    """
    if not opportunity.company or not opportunity.title:
        # Can't fuzzy match without these fields
        return False
    
    opp_company, opp_title = company_title_key(opportunity)
    
    for existing in existing_opportunities:
        if existing.id == opportunity.id:
            continue
        
        if not existing.company or not existing.title:
            continue
        
        exist_company, exist_title = company_title_key(existing)
        
        # Company must match closely
        company_match, company_exceeds = token_set_similarity(
            opp_company, exist_company, similarity_threshold,
        )
        
        if not company_exceeds:
            continue
        
        # Title must also match closely
        title_match, title_exceeds = token_set_similarity(
            opp_title, exist_title, similarity_threshold,
        )
        
        if title_exceeds:
            # It's a match! Log the similarity for debugging
            return True
    
    return False


def merge_sources(
    primary: Opportunity,
    duplicate: Opportunity,
) -> None:
    """Merge duplicate opportunity into primary, preserving all sources.

    Adds the duplicate's URL to primary's metadata if not already present.

    Args:
        primary: The primary opportunity record to keep
        duplicate: The duplicate to merge into primary
    """
    if not primary.metadata_:
        primary.metadata_ = {}
    
    if "source_urls" not in primary.metadata_:
        primary.metadata_["source_urls"] = []
    
    # Add primary URL if not already there
    if primary.url and primary.url not in primary.metadata_["source_urls"]:
        primary.metadata_["source_urls"].append(primary.url)
    
    # Add duplicate URL
    if duplicate.url and duplicate.url not in primary.metadata_["source_urls"]:
        primary.metadata_["source_urls"].append(duplicate.url)
    
    # Update last_seen_at to the more recent one
    if duplicate.last_seen_at and (
        not primary.last_seen_at or duplicate.last_seen_at > primary.last_seen_at
    ):
        primary.last_seen_at = duplicate.last_seen_at
