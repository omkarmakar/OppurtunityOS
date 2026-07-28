# OpportunityOS Production Audit — Phase 1 & 2 Complete

## Executive Summary
Successfully implemented schema fixes and advanced deduplication for OpportunityOS, establishing the foundation for the remaining phases.

---

## PHASE 1 — Schema Fixes ✓ COMPLETE

### What Was Done
1. **Extended Opportunity Model** (`database/models/opportunities.py`)
   - Added `company: str | None` — extracted and stored company name
   - Added `industry: str | None` — for industry classification
   - Added `posted_at: DateTime | None` — when job was actually posted
   - Added `deadline_at: DateTime | None` — application deadline as DateTime
   - Added `application_deadline_raw: str | None` — unparseable dates stored as raw string
   - Marked old `application_deadline` as deprecated but kept for backward compatibility

2. **Database Migration** (`database/migrations/versions/014_add_company_industry_dates.py`)
   - Created Alembic migration 014 with full up/down support
   - Verified on fresh SQLite database ✓
   - Includes proper indexes on company, industry, and deadline_at columns
   - Maintains backward compatibility with existing data

3. **Date Parsing Utility** (`services/search_pipeline/date_parser.py`)
   - `extract_company_name()` — finds "@Company" or "Company Name" patterns
   - `extract_posting_date()` — parses "Posted 3 days ago" and absolute dates
   - `extract_deadline_date()` — finds "Apply by Aug 15" patterns
   - `extract_metadata()` — unified extraction interface
   - Uses dateutil + regex patterns (no additional dependencies)
   - Falls back to NULL for unparseable dates (never fabricates)

4. **OpportunityCreator Integration**
   - Calls `extract_metadata()` on every opportunity's description
   - Sets company, posted_at, deadline_at directly from parsed content
   - Stores unparseable deadline as application_deadline_raw

### Verification Results
```
✓ Migration applies on fresh database
✓ All new columns present with correct types
✓ Indexes created successfully
✓ Sample job content parsed correctly:
  - Company: "TechCorp Inc" extracted from "@TechCorp Inc"
  - Posted at: 2026-07-23 (5 days ago)
  - Deadline at: 2026-08-15 (parsed from "Apply by Aug 15")
```

---

## PHASE 2 — Dedup Upgrade ✓ COMPLETE

### What Was Done
1. **Fuzzy Matching Utility** (`services/search_pipeline/dedup.py`)
   - `normalize_text()` — lowercase, strip prefixes (Senior, Junior, etc)
   - `token_set_similarity()` — uses difflib.SequenceMatcher for fuzzy matching
   - `company_title_key()` — extracts (company, title) tuple for dedup
   - `is_duplicate_by_company_title()` — checks if opportunity is duplicate
   - `merge_sources()` — merges duplicate URLs into metadata['source_urls']

2. **Two-Stage Deduplication in OpportunityCreator**
   - **Stage 1: Exact URL Match** (existing, unchanged)
     - Fast: O(1) lookup by URL
     - Skips if (user_id, url) pair already exists
   
   - **Stage 2: Fuzzy Match on (company, title)** (new)
     - Catches same job posted on multiple boards
     - Uses token-set similarity with 0.85 threshold
     - Scoped to same user+profile
     - Merges duplicate's URL into primary's metadata

3. **Source URL Tracking**
   - All board-specific URLs stored in `metadata_['source_urls']`
   - Primary opportunity URL kept in `url` field
   - Allows deduped opportunity to link to all original job postings

### Verification Results
```
✓ Text normalization works:
  "Senior Python Developer" → "python developer"
  "PYTHON DEVELOPER" → "python developer"
  "jr. Web Developer" → "web developer"

✓ Fuzzy matching correctly identifies:
  "Senior Developer" vs "Developer" → 100% match ✓
  
✓ Correctly rejects:
  "Python Developer" vs "Python Engineer" → 71% (below threshold)
  "React Frontend" vs "React JS" → 55% (below threshold)

✓ Source merging stores multiple URLs:
  metadata['source_urls'] = [
    "https://linkedin.com/jobs/1",
    "https://naukri.com/jobs/1"
  ]
```

---

## Technical Details

### Database Schema Changes
| Column | Type | Purpose |
|--------|------|---------|
| company | String(500) | Extracted company name |
| industry | String(200) | Industry classification |
| posted_at | DateTime | When job was posted (parsed) |
| deadline_at | DateTime | Application deadline (parsed) |
| application_deadline_raw | String(100) | Unparseable deadline strings |

### Indexes Added
- `ix_opportunities_company` — for filtering by company
- `ix_opportunities_industry` — for industry analysis
- `ix_opportunities_deadline_at` — for sorting by deadline

### Dependencies
- **No new external dependencies** — uses Python stdlib (difflib, dateutil already in use, regex)
- No rapidfuzz required — implemented equivalent with standard library

---

## What's Ready for PHASE 3

The foundation is now solid for:
1. **Embedding-based scoring** (default first pass)
2. **Gemini re-ranking for borderline opportunities** (55-75 score range)
3. **Skill gap analysis** — aggregate missing skills across opportunities
4. **Industry gap analysis** — suggest adjacent industries

All new schema fields are accessible and populated during opportunity creation.

---

## Files Modified / Created

### Created
- `services/search_pipeline/date_parser.py` (165 lines)
- `services/search_pipeline/dedup.py` (167 lines)
- `database/migrations/versions/014_add_company_industry_dates.py` (61 lines)

### Modified
- `database/models/opportunities.py` — added 5 new columns
- `services/search_pipeline/steps/opportunity_creator.py` — integrated extraction + two-stage dedup

### Testing
- All code tested with realistic job posting content
- Migration tested on fresh database
- No breaking changes to existing functionality

---

## Next Steps: PHASE 3

Ready to implement:
1. Keep EmbeddingOpportunityScorer as default first pass
2. Add second pass for borderline (55-75) opportunities with Gemini re-ranking
3. Create SkillGapAnalyzer to collect missing_skills and adjacent industries
4. Store and expose via API

**Commit Hash**: Latest commit includes all PHASE 1 & 2 work
