# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- **Groq AI provider support**: Integrated Groq as a second free-tier AI provider
  alongside OpenRouter. Groq offers no-credit-card-required free tier and
  officially documented rate limits (30 requests/minute, 500/day). New provider:
  - `GroqProvider` (`services/ai/groq_provider.py`): OpenAI-compatible API
    wrapper supporting verified free models (llama-3.3-70b-versatile,
    llama-3.1-8b-instant, mixtral-8x7b-32768 as of July 2026).
  - Handles Groq's unsupported fields gracefully (logprobs, logit_bias,
    top_logprobs) by filtering them before sending requests.
  - Distinguishes rate-limit errors (429) with clear error messages from Groq's
    response body (RPM vs RPD limits).
  - Registered in `AIRegistry.default()` with environment variable
    `OOS_AI__GROQ_API_KEY` and included in `/ai/providers` endpoint.
  - Full test coverage in `tests/services/test_groq_provider.py`.

### Fixed

- **BUG: OpenRouter provider using fake/unverified models**: The OpenRouter
  provider was using a non-existent default model ID (`"openrouter/free"`,
  which has no direct equivalent on OpenRouter's API) and a hardcoded
  `supported_models` list containing model IDs that do not exist or are not
  available as free-tier options on the platform (e.g. `"openai/gpt-4o:free"`,
  `"anthropic/claude-3.5-sonnet:free"`, `"google/gemini-2.0-flash:free"`).
  Fixed by:
  1. Changing the default model to `"meta-llama/llama-3.3-70b-instruct:free"`,
     a confirmed real and available free model on OpenRouter.
  2. Replacing the hardcoded list with a live-fetch mechanism
     (`_fetch_free_models()`) that queries OpenRouter's `/models` API endpoint,
     filters for models ending in `:free`, and caches the result for 1 hour.
  3. Adding a minimal verified fallback list
     (`_get_fallback_models()`) for robustness when the API is unreachable;
     this list contains only models confirmed to be real and free as of
     July 2026.
  4. Updating error messages to reflect the new default and removing references
     to the non-existent `"openrouter/free"` model.

- **BUG 1 — digest email never sent**: `_digest_callback` in
  `services/background/tasks.py` was calling `digest_svc.run(user_id)` with
  no `user_email` argument, so `DailyDigestService.run()` always skipped the
  `if self._email and user_email …` branch silently — no error, no log, no
  email — even when SMTP was fully configured. Fixed by looking up the `User`
  row via `UserRepository` before building the service and passing
  `user_email=user.email` into `run()`. If no row exists or the stored email
  is a placeholder, the callback now logs a clear warning
  (`"digest skipped: no user row / no email for user_id=…"`) and returns
  early instead of raising.

- **BUG 2 — no way to create a User row**: `database/models/users.py` defined
  the `User` model with `email` (unique, NOT NULL) and other models held hard
  foreign keys to `users.id`, but there was no `UserRepository`, no API
  endpoint, and no upsert path — making it impossible to store a real email
  address (required for BUG 1's fix) and silently fragile on Postgres where
  FK constraints are enforced. Fixed with four coordinated changes:
  - **`UserRepository.get_or_create`** (`database/repositories/user_repository.py`):
    returns the existing row or creates one; uses a synthetic
    `placeholder-<id>@no-email.invalid` when no real email is supplied so
    the NOT NULL constraint is always satisfied. Handles concurrent
    `IntegrityError` races.
  - **`GET/PUT /api/v1/users/{user_id}`** (`backend/api/v1/endpoints/users.py`,
    `backend/schemas/users.py`): `GET` returns 404 when the row is absent;
    `PUT` is an idempotent upsert — creates the row if missing then applies
    any supplied fields. This is the only way to store a real email for digest
    delivery.
  - **`POST /api/v1/profiles` guard** (`backend/api/v1/endpoints/profiles.py`):
    `create_profile` now calls `UserRepository.get_or_create(data.user_id)`
    before inserting the `Profile` row, ensuring the FK is always satisfied
    on Postgres (previously silently skipped on SQLite).
  - **`backend/api/v1/endpoints/__init__.py` / `backend/main.py`**: `users`
    router registered under `/api/v1`.

### Added

- **Calendar-Day Local-Time Window Scheduling** (`services/background/`):
  - Added `timezone` (default `"Asia/Kolkata"`), `pipeline_window_start_hour` (default 6), and `pipeline_window_end_hour` (default 12) to `BackgroundSchedulerSettings`.
  - Extended `ScheduledTask` in `services/background/scheduler.py` with `run_condition: Callable[[], bool] | None`. Updated `BackgroundScheduler._tick()` to evaluate `run_condition()` when present.
  - Added `SchedulerState` model ([scheduler_state.py](file:///c:/Users/omkar/Documents/Projects/COS/OpportunityOS/database/models/scheduler_state.py)) and repository ([scheduler_state_repository.py](file:///c:/Users/omkar/Documents/Projects/COS/OpportunityOS/database/repositories/scheduler_state_repository.py)) with Alembic migration `009_create_scheduler_state.py` to persist local calendar date (`last_run_date`) per user and task across app restarts.
  - Implemented `_make_pipeline_run_condition` closure in `services/background/tasks.py` using `zoneinfo.ZoneInfo`, ensuring the pipeline runs once per calendar day within the configured local time window.
  - Added startup check logging when the app starts past the daily window end hour without having run today.
  - Retained Option (a): digest task remains on its independent `digest_interval_seconds` schedule.
  - Added 5 unit tests in `tests/services/test_background_scheduler.py` covering window bounds, same-day duplicate prevention, next calendar day resets, and state persistence across process restarts.

- **Tavily Search Provider** (`services/search/tavily_provider.py`): replacement search provider for Brave Search (whose free tier was discontinued in Feb 2026). Features:
  - `TavilySearchProvider` class implementing `SearchProvider` interface with name `"Tavily"`
  - `TavilySettings` configuration domain in `core/config/settings.py` (`OOS_TAVILY__API_KEY`, `OOS_TAVILY__BASE_URL`)
  - Full request/response mapping (`query`, `max_results`, `search_depth`, `include_raw_content`)
  - Content snippet truncation capped at 500 characters
  - `raw_content` page text stored in `SearchResult.raw` for downstream step optimization
  - Error handling for missing API key (`RuntimeError`) and HTTP 429 rate limit / quota exhaustion
  - Registered in `SearchRegistry.default()` and available in `GET /api/v1/search-providers`
  - Documented in `.env.example` along with legacy Brave Search settings
  - 20 unit tests in `tests/services/test_tavily_provider.py` mocking `httpx.AsyncClient`

- **"Your Email" field in Settings page** (`frontend/pages/settings.py`): new
  **Account** section card (above Preferences) with a `QLineEdit` for the
  user's email address and a "Save Email" button. On load, `GET
  /users/{user_id}` is called and the stored email pre-populated (synthetic
  placeholders are suppressed). On save, `PUT /users/{user_id}` is called with
  inline green "Saved" / red error feedback. This is the only in-app way to
  set the email that drives digest delivery.

- **`tests/database/test_user_repository.py`**: covers `get_or_create`
  idempotency (8 cases), `get_by_email`, and the profile-creation FK path.

- **`tests/backend/test_users.py`**: covers `GET /users/{user_id}` (404 on
  miss, happy path, response shape), `PUT /users/{user_id}` (create, upsert
  idempotency, email update, placeholder fallback, `is_active` flag, 422 on
  invalid email), profile-auto-creates-user integration path, and the two
  digest-skip-gracefully paths (no row / placeholder email) via mocks.

- **Settings page rebuilt**: `frontend/pages/settings.py` is now a full settings UI with three sections:
  - **Integrations**: Renders `configuration_status` from `GET /settings` as a checklist with ✅/❌
    indicators, showing the exact env var to set for each missing integration (brave_search, openai,
    gemini, openrouter, ollama, dummyai). No secrets touch the UI.
  - **Preferences**: Theme (system/light/dark), language (en/fr/de/es/ja), notifications checkbox,
    default search provider dropdown (dummy/brave), default max_queries/max_results spinboxes.
    All fields are loaded from `GET /user-settings?user_id=...` and saved via `PUT /user-settings`.
  - **Digest Schedule**: Explains that digest config is currently file-only.
- **`GET/PUT /api/v1/user-settings` endpoint**: Backed by `ApplicationSettings` model +
  `ApplicationSettingsRepository.get_by_user_id()`/`upsert()`. Covers theme, language,
  notifications_enabled, notification_preferences, default_search_provider,
  default_max_queries, default_max_results.
- **Migration 007**: Adds `default_search_provider`, `default_max_queries`, `default_max_results`
  columns to `application_settings` table.
- **`configuration_status` block in `GET /api/v1/settings`**: Returns per-integration `{name,
  configured: bool, env_var, hint}` for braze_search, openai, gemini, openrouter, ollama, dummyai.
  Based purely on config key presence — never returns API keys or secrets.
- **ApplicationSettingsRepository extended**: Added `get_by_user_id()` and `upsert()` methods for
  the standard user-ID lookup and create-or-update patterns.
- **Bookmarks page rebuilt**: `frontend/pages/bookmarks.py` is now a full bookmarks list with:
  - `BookmarkRow` cards showing opportunity title/score/summary with clickable title
  - Inline notes editing via `QLineEdit` with "saved"/"error" feedback, persisted via
    `PATCH /bookmarks/{id}`
  - "Remove" button (calls `DELETE /bookmarks/{id}`) with automatic list refresh
  - Pagination controls matching the Opportunities page pattern
  - Empty state directing users to browse and bookmark opportunities
  - Offline fallback when the API is unreachable
- **Shared `OpportunityCard` widget**: `frontend/widgets/opportunity_card.py` extracted from
  `frontend/pages/opportunities.py` and now imported by both pages. DRY — single card
  definition used in Opportunities and Bookmarks pages.
- **`PATCH /api/v1/bookmarks/{id}` endpoint**: Allows notes-only update on bookmarks.
  Returns updated `BookmarkDetailResponse` with joined opportunity
  title/url/relevance_score. Returns 404 for missing bookmarks.
- **Search page rebuilt**: `frontend/pages/search.py` is now a full search-pipeline runner with:
  - Options card: search provider dropdown (populated from `GET /search-providers`), max queries
    spinbox (1-20), max results spinbox (1-50), skip AI ranking checkbox
  - "Run Search Now" button — prominent purple primary action button (matching app accent)
  - `QThread`-based execution so the synchronous `/pipeline/run` call never blocks the GUI
  - Indeterminate progress bar while running, button disabled during execution
  - Results summary panel on success (queries, results found, pages extracted, opportunities
    created, duplicates skipped, scored, notifications) with "View Results" button that
    navigates to the Opportunities page via `MainWindow._navigate(3)`
  - Error state on failure — error message shown in red (not silent fail)
  - "Last Run" section showing latest search timestamp and result count, fetched from
    `GET /searches/latest?user_id=...`
- **`GET /api/v1/search-providers` endpoint**: Lists available search provider names (dummy, brave
  if configured) via `SearchRegistry.default().list()`, sorted alphabetically
- **`GET /api/v1/searches/latest` endpoint**: Returns the most recent search for a user (id, query,
  result_count, last_run_at, created_at) — used by the search page's "Last Run" section
- **Frontend opportunities page rebuilt**: `frontend/pages/opportunities.py` is now a rich opportunity
  browser with: filter/sort bar (status dropdown, min-score spinbox, sort-by dropdown), scrollable card
  list with score badge (green/amber/red), clickable title via `QDesktopServices.openUrl`, summary,
  Strengths section, Gaps section (missing skills in red, concerns in amber), deadline, Bookmark button,
  Mark Applied status dropdown, pagination controls (Previous/Next, page indicator), empty state, loading
  spinner, offline fallback. Uses httpx synchronous calls matching profile.py pattern.
- **Opportunity deduplication**: `OpportunityCreator` pipeline step now checks for existing
  opportunities with the same `(user_id, url)` before creating a new row. If a match is found,
  `last_seen_at` is updated to the current timestamp and the row is reused instead of duplicated.
- **`last_seen_at` column**: New nullable `DateTime(timezone=True)` column on `opportunities`
  table tracks when an opportunity was last observed in search results.
- **Partial unique index**: A `CREATE UNIQUE INDEX ... WHERE url IS NOT NULL AND url != ''` on
  `(user_id, url)` prevents duplicate rows at the database level. Migration 006 cleans any
  existing duplicates before creating the index.
- **`opportunities_skipped_duplicate` field**: New field on `PipelineResult` and
  `PipelineResponse` so the API caller can see how many results were skipped as duplicates.
- **Alembic migration 006**: Adds `last_seen_at`, cleans duplicates, creates partial unique index.
- **Opportunities API**: Three new endpoints under `/api/v1/opportunities`:
  - `GET /opportunities` — paginated, filterable list (by status, min_score; sort by score or date)
  - `GET /opportunities/{id}` — full detail with all AI scoring fields (summary, pros, cons,
    required_skills, missing_skills, ranking_explanation, application_deadline, and more)
  - `PATCH /opportunities/{id}/status` — update status to new/reviewed/applied/interview/rejected/accepted
- **Bookmarks API**: Four endpoints under `/api/v1/bookmarks`:
  - `POST /bookmarks` — create a bookmark (returns 409 on duplicate)
  - `GET /bookmarks` — paginated list with joined opportunity title, url, and relevance_score
  - `PATCH /bookmarks/{id}` — update notes (added in P3)
  - `DELETE /bookmarks/{id}` — remove a bookmark

### Changed

- **services/search_pipeline/steps/opportunity_creator.py**: Added `_find_by_url()` helper and
  dedup logic. Opportunities with empty URLs always create a new row (logged as warning).
- **services/search_pipeline/pipeline.py**: `PipelineResult.opportunities_created` now counts
  only genuinely new rows; `opportunities_skipped_duplicate` reports skipped count.
- **backend/api/v1/endpoints/pipe.py**: `PipelineResponse` includes the new
  `opportunities_skipped_duplicate` field.
- **database/models/opportunities.py**: Added `last_seen_at` column and `__table_args__` with
  partial unique index definition.
- **backend/api/v1/endpoints/__init__.py**: Added `bookmarks` and `opportunities` routers.
- **backend/main.py**: Registered the new opportunities and bookmarks routers.

### Tests

- 4 new dedup tests in `tests/services/test_search_pipeline.py`:
  - `test_dedup_skips_duplicate_url` — first insert creates, second run with same URL skips
  - `test_dedup_empty_url_always_creates` — empty URL always inserts
  - `test_dedup_updates_last_seen_at` — repeat sighting bumps `last_seen_at`
  - Existing `test_execute_creates_opportunities` and `test_execute_empty_extracted` unchanged
- 10 new opportunity endpoint tests in `tests/backend/test_opportunities.py`:
  - Requires user ID, empty list, pagination, get by ID, get 404, status update, invalid status,
    status 404, filter by status, filter by min_score
- 6 new bookmark endpoint tests in `tests/backend/test_bookmarks.py`:
  - Create bookmark, duplicate 409, missing opportunity 404, delete, delete 404, list, pagination

## [0.9.0] - 2026-07-25

### Added

- **Thread safety**: Added `threading.Lock` to `BackgroundScheduler._tasks` dict (add/remove/get/list are now atomic); `AICache` all public methods (get, set, clear, size, invalidate); `TokenCounter` singleton uses double-checked locking
- **Security**: SSRF protection in `ContentExtractor._validate_url()` — blocks private/reserved IPs (10/8, 172.16/12, 192.168/16, 127/8, 169.254/16, ::1, fc00::/7, fe80::/10), localhost, .local/.internal/.lan hostnames, and non-http schemes
- **Security**: Gemini API key moved from query string (`?key=...`) to `x-goog-api-key` header (prevents credential leakage in request logs)
- **Security**: Credential redaction in `GET /api/v1/settings` — database passwords are replaced with `****` in the response
- **Security**: In-memory sliding-window rate limiter middleware — `RateLimitMiddleware` with per-route limits (10 req/min for AI, 5 req/min for pipeline, 20 req/min for content extraction); exempts health/version; disabled in debug mode
- **Performance**: Parallel AI scoring — `score_multiple_and_save()` uses `asyncio.Semaphore(5)` + `asyncio.gather()` to score opportunities concurrently instead of sequentially
- **Performance**: N+1 query fix in dashboard — bookmark rows use `joinedload(Bookmark.opportunity)`; bookmark ID set queries only `opportunity_id` column instead of full ORM objects
- **Performance**: Deferred SQLAlchemy engine — `create_engine()` moved from module import time to first-use via `get_engine()` with `__getattr__` module proxy (faster startup, avoids side effects)
- **Performance**: Dashboard response caching — `QueryCache` with 15-second TTL caches the full dashboard response per user
- **Caching**: Generic `QueryCache` utility — thread-safe TTL cache with `get_or_set()`, `invalidate()`, `invalidate_pattern()`, `max_size` eviction
- **Error handling**: Bare `except: pass` in `SearchExecutor` replaced with `logger.warning` (search query failures are now visible); AI registry and search registry `except Exception: pass` replaced with `logger.debug` (failures are logged at debug level); content extractor step failures logged at warning level
- **Documentation**: Docstrings added to `QueryCache`, `RateLimitMiddleware`, `BackgroundScheduler._tick()`
- **Tests**: 37 new tests across 5 new test files:
  - `test_cache.py` — 9 tests: get/set, miss, get_or_set, expiry, invalidate, pattern invalidate, max-size eviction, thread safety, clear
  - `test_thread_safety.py` — 5 tests: AICache concurrent access, AICache clear-during-read, TokenCounter singleton, scheduler concurrent add/remove, scheduler tasks property snapshot
  - `test_rate_limit.py` — 4 tests: normal requests pass, excess blocked, health exempted, route-specific limits
  - `test_settings_redaction.py` — 4 tests: password redacted, no-password unchanged, username-only, empty URL
  - `test_content_extractor_security.py` — 13 tests: 10 private/internal URL rejections + 3 allowed external URL validations

### Changed

- **database/session.py**: `engine` is now lazily initialized via `get_engine()` with `__getattr__` module proxy; `SessionLocal` still eagerly initialized but triggers engine lazily
- **backend/main.py**: `_scheduler` type changed from `Any` to `BackgroundScheduler | None`; rate limiter only active when `cfg.debug == False`
- **services/cache.py**: New file — generic `QueryCache` class
- **backend/middleware/rate_limit.py**: New file — `RateLimitMiddleware` Starlette middleware
- **backend/utils/__init__.py**: Removed (empty directory deleted)
- **frontend/pages/profile.py**: Removed unused `QCheckBox` import
- **frontend/pages/notifications.py**: Removed unused `QFont` import
- **tests/database/test_models.py**: Removed unused `text` import
- **tests/services/test_search_providers.py**: Removed unused `os`, `asyncio` imports
- **services/content_extractor/extractor.py**: Extended with `_validate_url()` SSRF guard and `_BLOCKED_NETWORKS` constant

## [0.8.0] - 2026-07-25

### Added

- Plugin-style search provider architecture (`services/search/`):
  - `SearchProvider` — abstract base with `name` property and `async search(query, count, offset)` method
  - `SearchResult` dataclass (title, url, snippet, source, raw)
  - `SearchRegistry` — provider registry with `register()`, `get()`, `list()`, and `default()` factory
- `BraveSearchProvider` — real Brave Search API integration via httpx, requires API key
- `DummyProvider` — hardcoded test/development provider (no external dependencies)
- `BraveSearchSettings` config model with `api_key` and `base_url` fields
- Config wiring: `AppConfig.brave_search` nested settings domain (env var: `OOS_BRAVE_SEARCH__API_KEY`)
- `pytest-asyncio` dev dependency with `asyncio_mode = "auto"`
- 14 search provider tests (SearchResult, DummyProvider, BraveProvider error handling, Registry CRUD + custom provider registration)

### Changed

- **core/config/settings.py**: Added `BraveSearchSettings` domain; integrated into `AppConfig`

## [0.7.0] - 2026-07-25

### Added

- Resume parsing module (`services/resume_parser/`) — deterministic extraction without AI:
  - `file_reader.py` — reads `.pdf` (pypdf) and `.docx` (python-docx) to plain text
  - `parser.py` — section-based parser detecting `SKILLS`, `EXPERIENCE`, `EDUCATION`, `PROJECTS` headers; uses regex for dates, bullet-point descriptions, comma-separated skill lists
  - `ParseResult` dataclass with `skills`, `projects`, `education`, `experience` fields
- Two API endpoints:
  - `POST /api/v1/resume/parse` — upload resume file, returns parsed data without storing
  - `POST /api/v1/resume/parse-and-save/{user_id}` — parse and update profile in one call
- `projects` JSON column on `profiles` table + Alembic migration 003
- `ProjectEntry` Pydantic schema (name, description, technologies, url)
- `ResumeParseResponse` schema with all parsed sections
- GUI integration: "Resume Parser" section on Profile page — Browse + Parse & Fill button auto-populates skills, education, experience, and projects from a selected PDF/DOCX
- Dependencies: `pypdf`, `python-docx`, `python-multipart`
- 5 resume API tests covering DOCX parsing, section detection, invalid file rejection, parse-and-save flow, and missing profile handling

### Changed

- **database/models/profiles.py**: Added `projects` JSON column
- **backend/schemas/profiles.py**: Added `ProjectEntry` schema; `projects` field in `ProfileCreate`, `ProfileUpdate`, `ProfileResponse`; new `ResumeParseResponse` schema
- **frontend/pages/profile.py**: Added resume upload section with browse and parse-and-fill functionality

## [0.6.0] - 2026-07-25

### Added

- Profile management with full CRUD (database, API, GUI):
  - **Database**: 11 new columns on `profiles` table — `education` (JSON), `experience` (JSON), `skills` (JSON), `preferred_locations` (JSON), `salary_expectations`, `target_companies` (JSON), `keywords` (JSON), `resume_path`, `linkedin_url`, `github_url`, `portfolio`
  - **Migration 002**: Alembic upgrade adds all columns; downgrade removes them
  - **API**: `POST/GET/PUT/DELETE /api/v1/profiles/{user_id}` with Pydantic request/response schemas (`ProfileCreate`, `ProfileUpdate`, `ProfileResponse`, `EducationEntry`, `ExperienceEntry`)
  - **Repository**: `ProfileRepository.get_by_user_id()` and `upsert()` methods
  - **GUI**: Full profile form with sections — Basic Info, Education (add/remove entries via dialog), Experience (add/remove entries via dialog), Skills, Preferred Locations, Target Companies, Keywords (tag inputs), Salary Expectations, Links & Documents (Resume, LinkedIn, GitHub, Portfolio)
  - **API integration**: GUI connects to backend via httpx; Load/New/Save/Delete workflow with user ID entry
  - 9 profile API tests covering create, duplicate (409), get, update, delete, nonexistent (404), and full field response

### Changed

- **database/models/profiles.py**: Extended with 11 new mapped columns for profile management
- **database/repositories/profile_repository.py**: Added `get_by_user_id()` and `upsert()` methods
- **database/migrations/alembic.ini**: Fixed `script_location` and `prepend_sys_path` for correct path resolution
- **backend/api/v1/endpoints/profiles.py**: New CRUD router registered in main.py
- **frontend/pages/profile.py**: Replaced placeholder with full interactive form

## [0.5.0] - 2026-07-25

### Added

- FastAPI backend with full API structure:
  - `GET /api/v1/health` — returns status + database connectivity check
  - `GET /api/v1/version` — returns app name, version, Python runtime
  - `GET /api/v1/settings` — returns full serialized config (domains: database, logging, server, plugins, paths)
- Pydantic response schemas (`backend/schemas/`) with OpenAPI/Swagger documentation
- Dependency injection via `FastAPI Depends`:
  - `get_db()` — database session
  - `get_app_config()` — application configuration
  - `get_config_provider()` — configuration provider
- Lifespan-based startup (`init_db()` on application start)
- 15 API endpoint tests (health, version, settings)

### Changed

- **backend/main.py**: Replaced deprecated `on_event` with `lifespan` context manager; includes health, version, and settings routers
- **backend/api/v1/endpoints/health.py**: Extended with database connectivity check via `SELECT 1`
- **backend/api/deps.py**: Added `get_app_config()` and `get_config_provider()` DI functions

## [0.4.0] - 2026-07-25

### Added

- Desktop application shell with PySide6
- Dark theme stylesheet (`frontend/theme.py`) — deep dark palette (#0f0f1a bg, purple accent #7c3aed)
- Sidebar navigation (`frontend/widgets/sidebar.py`) — 8 nav items with unicode icons, active state highlighting, brand header, version footer
- 8 placeholder page widgets (`frontend/pages/`):
  - `DashboardPage`, `ProfilePage`, `SearchPage`, `OpportunitiesPage`
  - `BookmarksPage`, `NotificationsPage`, `SettingsPage`, `LogsPage`
- `PageWidget` base class with header, separator, and centered placeholder content
- `QStackedWidget` page switching driven by sidebar signals
- Resizable window (min 1024×768, default 1280×800)
- Status bar with navigation feedback
- 5 Qt GUI tests covering window properties, sidebar, page stack, and navigation

### Changed

- **frontend/windows/main_window.py**: Replaced stub with full sidebar + stacked page layout
- **pyproject.toml**: Added `pytest-qt` dev dependency for Qt GUI testing

## [0.3.0] - 2026-07-25

### Added

- Complete database layer with SQLAlchemy ORM models for 8 domain entities:
  - `users`, `profiles`, `sources`, `searches`, `opportunities`, `bookmarks`, `notifications`, `application_settings`
- Generic `BaseRepository[ModelT]` with `get/list/add/update/delete/count/exists`
- 8 concrete repository classes (`UserRepository`, `ProfileRepository`, `SourceRepository`, `SearchRepository`, `OpportunityRepository`, `BookmarkRepository`, `NotificationRepository`, `ApplicationSettingsRepository`)
- Initial Alembic migration (`001_create_all_tables.py`) — creates all 8 tables with FK constraints, indexes, and unique constraints
- Repository pattern with filter support (`list(**filters)`, `count(**filters)`)
- Relationship query methods on concrete repos (`get_with_profile`, `get_with_sources`, `list_by_status`, `count_by_priority`)
- UUID primary keys, server-default timestamps, cascade deletes on user
- 47 database tests covering table schema, model CRUD, relationships, constraints, timestamps, and repository operations

### Changed

- **pyproject.toml**: Added `[tool.hatch.build.targets.wheel]` packages config for build system compatibility
- **database/migrations/env.py**: Imports `database.models` for Alembic autodetection
- **database/session.py**: Imports models before `Base.metadata.create_all()` in `init_db()`
- **database/__init__.py**: Exports all models, repositories, session, engine, init_db

## [0.2.0] - 2026-07-25

### Added

- Complete configuration system with three-tier loading
- `AppConfig` Pydantic model with nested settings domains:
  - `DatabaseSettings` (url, echo, pool_size, max_overflow)
  - `LoggingSettings` (level, rotation, retention, directory)
  - `ServerSettings` (host, port, allowed_origins)
  - `PluginSettings` (enabled_plugins, plugin_dir)
  - `PathSettings` (data_dir, config_dir, log_dir, asset_dir)
- Input validation with Pydantic field validators:
  - Environment must be one of development/testing/production
  - Port range validation (1–65535)
  - Log level must be a valid Loguru level
  - Database URL scheme validation
- Auto-load `get_config()` singleton with lazy initialisation
- `reload_config()` for testing and environment switching
- `ConfigurationProvider` class for dependency injection
- Environment overrides via `OOS_*` prefixed env vars with `__` nested delimiter
- Environment-specific YAML files: `testing.yaml`, `production.yaml`
- Deep-merge algorithm for multi-environment YAML layering
- `OOS_CONFIG_DIR` env var for custom config directory resolution
- `python-dotenv` for `.env` file support

### Changed

- **database/session.py**: Engine and session factory now derive from
  `get_config()` instead of a flat module-level settings object
- **backend/core/config.py**: Delegates to unified `AppConfig` via
  `get_backend_config()`
- **backend/core/logging.py**: Reads log level, rotation, retention from config
- **backend/main.py**: Uses config for title, version, debug, CORS origins
- **.env.example**: Updated to `OOS_*` prefix format with all documented options
- YAML config files restructured to match Pydantic model hierarchy

### Removed

- Standalone `AppSettings(BaseSettings)` in `core/config/settings.py`
  (replaced by the multi-domain `AppConfig` model)

## [0.1.0] - 2026-07-25

### Added

- Project scaffold with clean architecture layout
- FastAPI backend with health endpoint
- PySide6 GUI application stub
- SQLAlchemy ORM with Alembic migrations
- Loguru logging configuration
- Pydantic settings management
- YAML-based configuration
- Plugin system base classes
- Service layer abstractions
- Test suite with pytest
- Ruff and Black code quality tooling
- uv package manager configuration
- MIT License
