"""Date and metadata extraction utilities for job opportunities.

Extracts posting dates, deadlines, company names, and other structured
metadata from unstructured job description content using regex patterns
and dateutil parsing.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional

from dateutil import parser as date_parser

# Common date patterns in job postings
DATE_PATTERNS = [
    # ISO format: 2026-07-28, 2026/07/28
    (r"\d{4}[-/]\d{2}[-/]\d{2}", "iso"),
    # US format: July 28, 2026 or Jul 28, 2026
    (r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}", "us"),
    # EU format: 28 July 2026 or 28.07.2026
    (r"\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}", "eu"),
    # Relative: Posted 3 days ago, Posted on 2 weeks ago
    (r"(?:Posted|posted|Deadline|deadline)\s+(?:on\s+)?(\d+)\s+(?:day|week|month)s?\s+ago", "relative"),
]

# Company name patterns
COMPANY_PATTERNS = [
    # At company name pattern: "Senior Dev @ Company Inc"
    r"@\s+([A-Za-z0-9\s&\.\,\-\']+?)(?:\s+\(|$|,|\n)",
    # Company: pattern
    r"(?:Company|Employer|Organization):\s*([A-Za-z0-9\s&\.\,\-\']+?)(?:$|\n|,)",
    # We are hiring / We're looking pattern - followed by company
    r"(?:We are|We're)\s+(?:currently\s+)?hiring\s+(?:at|for)\s+([A-Za-z0-9\s&\.\,\-\']+?)(?:\s+to|\.|$)",
]


def extract_company_name(content: str) -> Optional[str]:
    """Extract company name from job description content.

    Args:
        content: Raw job description text

    Returns:
        Extracted company name or None if not found
    """
    if not content:
        return None

    content = content.strip()

    for pattern in COMPANY_PATTERNS:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if match:
            company = match.group(1).strip()
            # Clean up common false positives
            if company and len(company) < 200 and not company.lower().startswith(("http", "www")):
                return company

    return None


def extract_posting_date(content: str) -> Optional[datetime]:
    """Extract job posting date from content using relative or absolute patterns.

    Args:
        content: Raw job description text

    Returns:
        Extracted datetime or None if not found or parseable
    """
    if not content:
        return None

    content = content.strip()

    # Check for relative dates first (e.g., "Posted 3 days ago")
    relative_match = re.search(
        r"(?:Posted|posted)\s+(?:on\s+)?(\d+)\s+(day|week|month)s?\s+ago",
        content,
        re.IGNORECASE,
    )
    if relative_match:
        num = int(relative_match.group(1))
        unit = relative_match.group(2).lower()
        now = datetime.now()
        
        if unit.startswith("day"):
            return now - timedelta(days=num)
        elif unit.startswith("week"):
            return now - timedelta(weeks=num)
        elif unit.startswith("month"):
            return now - timedelta(days=30 * num)

    # Try to find absolute dates
    for pattern, date_format in DATE_PATTERNS[:-1]:  # Skip relative, already handled
        match = re.search(pattern, content)
        if match:
            date_str = match.group(0)
            try:
                return date_parser.parse(date_str, fuzzy=False)
            except (ValueError, date_parser.ParserError):
                continue

    return None


def extract_deadline_date(content: str) -> Optional[datetime]:
    """Extract application deadline from content.

    Looks for patterns like "Apply by", "Deadline", "Applications close", etc.

    Args:
        content: Raw job description text

    Returns:
        Extracted deadline datetime or None if not found
    """
    if not content:
        return None

    content = content.strip()

    # Look for deadline/apply-by patterns
    deadline_patterns = [
        r"(?:Apply by|Deadline|Applications close|Closing date|Must apply by|Application deadline)[\s:]+(.+?)(?:\n|\.|\s{2}|$)",
        r"(?:Until|through|by)\s+(.+?)(?:\n|\.|\s{2}|$)",
    ]

    for pattern in deadline_patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if match:
            date_str = match.group(1).strip()
            # Clean up trailing punctuation
            date_str = re.sub(r"[,\.]$", "", date_str)
            
            try:
                # Try parsing with dateutil
                parsed = date_parser.parse(date_str, fuzzy=True, default=datetime.now().replace(year=datetime.now().year))
                # Adjust year if deadline appears to be in the past
                if parsed < datetime.now():
                    parsed = parsed.replace(year=parsed.year + 1)
                return parsed
            except (ValueError, date_parser.ParserError):
                continue

    return None


def extract_metadata(content: str) -> dict[str, Optional[str | datetime]]:
    """Extract all structured metadata from job description.

    Args:
        content: Raw job description text

    Returns:
        Dictionary with extracted company, posted_at, and deadline_at
    """
    return {
        "company": extract_company_name(content),
        "posted_at": extract_posting_date(content),
        "deadline_at": extract_deadline_date(content),
    }
