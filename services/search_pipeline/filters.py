"""URL and query quality filters for the search pipeline.

Filters out low-quality results that waste content extraction budget:
- Job board listing/index pages (not actual job postings)
- Forum threads, Q&A sites, blog posts about job searching
- Generic career advice pages
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Domains that are job board INDEX pages (not actual job postings).
# These return search results pages, not individual jobs.
# NOTE: We do NOT blacklist ATS domains (greenhouse, lever, workday, etc.) as they host individual jobs.
_JUNK_DOMAINS: frozenset[str] = frozenset({
    # Job board search/listing pages — only block when used as listing pages
    "monster.com",
    "careerbuilder.com",
    "simplyhired.com",
    "snagajob.com",
    "talent.com",
    "jooble.org",
    "neuvoo.com",
    "careerjet.com",
    "jobtome.com",
    "jobisjob.com",
    "jobook.com",
    "joblift.com",
    "jobcase.com",
    "jobright.ai",
    "jobboardsearch.com",
    # Generic job aggregators — listing pages
    "naukri.com",
    # Forum / Q&A / advice sites
    "reddit.com",
    "quora.com",
    "stackoverflow.com",
    "stackexchange.com",
    "medium.com",
    "substack.com",
    # Career advice sites
    "theladders.com",
    "careercast.com",
    "careernetwork.com",
    "themuse.com",
    # Government / general pages
    "dol.gov",
    "usa.gov",
    "usajobs.gov",
})

# URL path patterns that indicate listing/index pages
_INDEX_PATH_PATTERNS: list[re.Pattern[str]] = [
    # Job board search/listing pages (not individual job postings)
    re.compile(r"/jobs$", re.IGNORECASE),  # /jobs (listing page)
    re.compile(r"/jobs/q-", re.IGNORECASE),  # /jobs/q-python-developer (search results)
    re.compile(r"/jobs\?", re.IGNORECASE),  # /jobs?q=... (search query)
    re.compile(r"/jobs/search", re.IGNORECASE),  # /jobs/search/ (LinkedIn search)
    re.compile(r"/Job/.*-SRCH_", re.IGNORECASE),  # Glassdoor /Job/...-SRCH_ (search)
    re.compile(r"/browse/", re.IGNORECASE),
    re.compile(r"/category/", re.IGNORECASE),
    re.compile(r"/listings$", re.IGNORECASE),
    re.compile(r"/career-advice", re.IGNORECASE),
    re.compile(r"/blog/", re.IGNORECASE),
]

# Title patterns that indicate non-job content
_JUNK_TITLE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^Q:\s*What\s+is", re.IGNORECASE),
    re.compile(r"^How\s+to\s+(find|get|apply|write|build)", re.IGNORECASE),
    re.compile(r"^What\s+is\s+a\s+\w+\s+job", re.IGNORECASE),
    re.compile(r"^\d+\+?\s+(entry.?level|junior|graduate|intern)", re.IGNORECASE),
    re.compile(r"^Browse\s+\d+", re.IGNORECASE),
    re.compile(r"^Top\s+\d+\s+(entry|junior|graduate)", re.IGNORECASE),
    re.compile(r"^(Best|Top)\s+(entry|junior|graduate)\s+jobs", re.IGNORECASE),
    re.compile(r"^Entry.?Level\s+Jobs?\s+(in|near)", re.IGNORECASE),
    re.compile(r"^Junior\s+Jobs?,?\s+Employment", re.IGNORECASE),
    re.compile(r"\d+\+?\s+Entry.?Level\s+(Developer|Software|Engineer)", re.IGNORECASE),
]


def is_junk_url(url: str) -> bool:
    """Check if a URL points to a low-quality listing/index page.

    Returns True if the URL should be skipped during content extraction.
    """
    if not url:
        return False

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().removeprefix("www.")

        # Check domain blacklist
        for junk_domain in _JUNK_DOMAINS:
            if domain == junk_domain or domain.endswith("." + junk_domain):
                return True

        # Check path patterns
        path = parsed.path
        for pattern in _INDEX_PATH_PATTERNS:
            if pattern.search(path):
                return True

    except Exception:
        pass

    return False


def is_junk_title(title: str) -> bool:
    """Check if a title indicates a non-job page (listing page, advice, Q&A).

    Returns True if the title looks like a listing page or generic content.
    """
    if not title:
        return False

    for pattern in _JUNK_TITLE_PATTERNS:
        if pattern.search(title):
            return True

    return False


def is_quality_job_url(url: str, title: str = "") -> bool:
    """Quick check if a URL+title combo looks like an actual job posting.

    Returns False for listing pages, index pages, advice articles, etc.
    """
    if is_junk_url(url):
        return False
    if is_junk_title(title):
        return False
    return True
