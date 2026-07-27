# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- **Frontend simplification for resume-slot model (P34)**:
  - `TargetingForm` (`frontend/widgets/profile_form.py`) replaces the old full `ProfileForm` — only exposes slot name, preferred locations, remote preference, salary expectations, and target companies as editable fields.
  - `ProfilePage` (`frontend/pages/profile.py`) is rewritten for per-slot flow: horizontal switcher shows `SlotCard`s (with name + skill/location-derived subtitle, no delete button); selecting a slot loads the read-only parsed data (skills as chips, education/experience/projects as sub-cards) and the `TargetingForm` for targeting fields; the upload-resume flow pre-fills the parsed sections and switches to create mode.
  - `SearchPage` (`frontend/pages/search.py`) profile-combo now includes an "All Profiles (N slots)" option that triggers `MultiPipelineWorker` — runs the search pipeline for every slot sequentially and displays aggregate totals ("X total results across N pipelines").
  - Tests: `tests/frontend/test_profile_page.py` rewritten for `SlotCard`/`NewSlotCard`/`SectionCard`/`TargetingForm`/`ProfilePage` (18 tests); `tests/frontend/test_search_page.py` updated for the new "All Profiles" combo entry.

- **Per-profile pipeline scheduler (P32)**: The background scheduler now registers one independent ``ScheduledTask`` per user profile (task name ``"pipeline:{profile_id}"``) instead of a single user-level task. Each profile's daily search window is tracked independently via its own ``SchedulerState`` row, so one profile failing never blocks another, and a profile that already completed today is correctly skipped while others still due are run.
  - ``database/models/scheduler_state.py`` — added nullable ``profile_id`` column (FK to ``profiles.id``); changed ``UniqueConstraint`` from ``(user_id, task_name)`` to ``(user_id, profile_id, task_name)`` so that ``NULL`` profile_id is used for user-level tasks (e.g. ``"digest"``) while pipeline rows carry a real profile_id.
  - ``database/migrations/versions/012_scheduler_state_per_profile.py`` — Alembic migration 012.
  - ``database/repositories/scheduler_state_repository.py`` — all three methods (``get_by_user_and_task``, ``get_or_create``, ``update_last_run``) accept an optional ``profile_id`` parameter and include it in lookups/upserts.
  - ``services/background/tasks.py`` — ``_make_pipeline_run_condition`` and ``_pipeline_callback`` now accept a ``profile_id`` and operate on that single profile; ``create_and_start_scheduler`` fetches the user's profiles at startup and registers one task per profile; a new ``_check_and_log_missed_window`` helper reports per-profile missed-window diagnostics; new profiles added while the app is running require a restart (noted in docstring).
  - Tests: 34 tests in ``test_background_scheduler.py`` (3 new multi-profile isolation tests), all passing.

### Added

- **Resume-as-profile architecture (P31)**: Profile model now has `raw_extracted_text`, `resume_filename`, `resume_uploaded_at`, and `remote_preference` columns. The first three are auto-populated by the resume upload-and-save flow; `remote_preference` is a user-editable targeting field alongside `preferred_locations`, `salary_expectations`, and `target_companies`.
  - `core/config/settings.py` — new `ProfileSettings.max_slots_per_user` (default 10) replaces the hardcoded `MAX_PROFILES_PER_USER = 5` in the profiles endpoint.
  - `database/models/profiles.py` — added four new columns.
  - `database/migrations/versions/011_resume_as_profile.py` — Alembic migration adding the columns.
  - `backend/schemas/profiles.py` — `ProfileCreate`/`ProfileUpdate` now accept `remote_preference`; `ProfileResponse` exposes all four new fields.
  - `backend/api/v1/endpoints/profiles.py` — slot cap is read from `AppConfig().profiles.max_slots_per_user` instead of a hardcoded constant.
  - `backend/api/v1/endpoints/resume.py` — refactored `parse_and_save` to store `raw_extracted_text`, `resume_filename`, and `resume_uploaded_at` on the profile; file is kept permanently in `data/resumes/`.
  - `services/search_pipeline/steps/query_generator_rules.py` — when `raw_extracted_text` is non-empty, extracts additional skills via the shared vocabulary and includes `remote_preference` in the location list.
  - `services/opportunity_scorer/embedding_scorer.py` — `_build_profile_text()` prefers `raw_extracted_text` as the primary embedding source when available.
  - `frontend/pages/profile.py` — `MAX_PROFILES` updated from 5 to 10 to match the new backend default.
  - Tests: backend profile CRUD tests updated for 10-slot cap and new response fields.

### Added

- **Rule-based QueryGenerator backend (default, no AI required)**: The
  `QueryGenerator` pipeline step previously made an LLM call via
  `generate_with_fallback` on every pipeline run just to concatenate profile
  fields (skills, roles, locations, companies, keywords, education) with
  domain keywords into search query strings — pure templating, not generation.
  - `services/search_pipeline/steps/query_generator_rules.py` — new
    `RuleBasedQueryGenerator` class implementing the same `PipelineStep`
    interface. Combines every profile field with bundled plugin keyword sets
    via template expansion (e.g. `"{skill} {role} {location}"`,
    `"{skill} {plugin_keyword}"`, `"{role} jobs"`). Deduplicates, caps at
    the configured query count, and returns fallback queries when the profile
    has almost no data. No AI provider is ever called.
  - `core/config/settings.py` — new `QueryGenerationSettings` nested model
    with a `backend: str = "rules"` field (`"rules"` or `"llm"`) inside
    `AISettings.query_generation`, configurable via
    `OOS_AI__QUERY_GENERATION__BACKEND`.
  - `services/search_pipeline/steps/query_generator.py` — new
    `create_query_generator()` factory function that reads the config backend
    and returns either `RuleBasedQueryGenerator` or the original
    `QueryGenerator`. The single call site in `pipeline.py` now uses the
    factory instead of constructing `QueryGenerator` directly.
  - The old LLM-based `QueryGenerator` is kept completely intact and
    functional — flip `backend` back to `"llm"` to restore previous
    behaviour unchanged.
  - Tests: `tests/services/test_query_generator_rules.py` — 17 tests
    covering candidate generation (full profile, empty profile, skills-only,
    roles-only, plugin keyword integration), query selection (dedup, cap,
    under-cap, fallback), execute integration (ctx key, missing profile,
    plugin keywords in output, cap honoured, fallback on empty, provider
    tracking), and factory switching (default returns rules, `"llm"` config
    returns `QueryGenerator`).

- **Embedding-based OpportunityScorer backend (default, no AI required)**:
  The `OpportunityScorer` previously made one LLM call per opportunity (the
  single most expensive pipeline step) via `generate_with_fallback` to
  produce relevance_score, summary, pros, cons, required_skills,
  missing_skills, ranking_explanation — and `application_deadline`.
  This replaces it with a local sentence-embedding model for the numeric
  score and rule-based logic for everything else; no network call, no LLM
  dependency. The exact same `ScoredOpportunity` dataclass shape is
  preserved so all call sites are unaffected.
  - `services/opportunity_scorer/embedding_scorer.py` — new
    `EmbeddingOpportunityScorer` class exposing the same three public
    methods (`score_opportunity`, `score_and_save`,
    `score_multiple_and_save`) as the LLM-based `OpportunityScorer`.
  - **Relevance score**: Loads `sentence-transformers/all-MiniLM-L6-v2`
    (~80 MB) once at module level — subsequent instantiation in the same
    process reuses the cached model. Builds profile embedding text using
    the identical field-combining logic as `_build_profile_context` in
    `scorer.py` (skills, roles, locations, companies, keywords, education,
    experience). Computes cosine similarity between profile and opportunity
    embeddings, then applies a sigmoid calibration
    (`1/(1+exp(-10*(sim-0.35)))`) to spread scores across the full 0-100
    range instead of concentrating them in the narrow band raw cosine
    similarity produces. Scores match downstream UI thresholds (green ≥70,
    amber ≥40, red <40) sensibly.
  - **required_skills / missing_skills**: Rule-based, not embedding-based.
    A static frozenset of ~280 common technical/domain skill terms
    (software, hardware, research, business) is defined in the file.
    `_extract_skills_from_text` does a case-insensitive substring match
    against the opportunity's title+description. `missing_skills` =
    required_skills not present in `profile.skills`.
  - **pros / cons / summary / ranking_explanation**: Template-based, no
    generated prose. Summary: `"{title} — {score}% relevance, {n} skills
    identified, {m} of your skills apply."` Pros: one line per matched
    skill/keyword overlap plus any target_company match. Cons: one line
    per missing_skill, capped at 5. ranking_explanation: deterministic
    sentence referencing the actual cosine similarity score and skill
    overlap count.
  - **application_deadline**: Left as empty string — the LLM was the only
    path that could extract this. A separate rule-based date-extraction
    pass could be added later.
  - Dependencies: `sentence-transformers>=3.4.0` added to `pyproject.toml`.
    This transitively pulls `torch` (CPU-only on PyPI for Windows — no
    CUDA build). Installed size ~800 MB–1 GB for torch alone, making this
    by far the heaviest dependency in the project.
  - `core/config/settings.py` — new `scoring_backend: str = "embedding"`
    field on `AISettings` (alongside the existing `query_generation`
    backend), configurable via `OOS_AI__SCORING_BACKEND`. `"embedding"`
    (default) uses the local model; `"llm"` restores the original AI call.
  - `services/opportunity_scorer/embedding_scorer.py` — new
    `create_opportunity_scorer()` factory function (mirroring P27's
    `create_query_generator` pattern) that reads the config backend and
    returns the appropriate scorer.
  - **Both call sites updated** to use the factory:
    `services/search_pipeline/steps/ranking.py` (AIRankingStep) and
    `backend/api/v1/endpoints/scoring.py` (both `/opportunities/score`
    and `/opportunities/score-and-save`). No structural changes needed
    — the factory returns an object with the same interface.
  - The old LLM-based `OpportunityScorer` is kept completely intact and
    functional — flip `scoring_backend` back to `"llm"` to restore
    previous behaviour unchanged.
  - **Expected latency difference**: The LLM path makes one external API
    call per opportunity (sequential with semaphore), typically 1–5 s per
    call → 5–25 s for 5 opportunities. The embedding path loads the model
    once (a few seconds on first import, cached thereafter) then computes
    all scores locally with sub-second total latency for any batch size.
    Users will perceive the pipeline as finishing nearly instantly once
    scoring begins.
  - Tests: `tests/services/test_embedding_scorer.py` — 30 tests covering
    `_cosine_sim_to_score` calibration (extremes, midpoint, low/high sim,
    monotonicity), `_build_profile_text` (empty, full), `_extract_skills`
    (known, compound, case-insensitive, empty), integration tests with
    real model (matching > unrelated, all fields returned, required/
    missing skill extraction, `score_and_save` updates opportunity,
    `score_multiple_and_save` sorts descending, empty profile, empty list,
    pros includes matched skills and target company, cons lists missing
    skills), and factory switching (default returns embedding, config-
    driven `"llm"` returns `OpportunityScorer`, env-var override).

- **Optional LLM narrative enrichment for embedding scorer (opt-in, off
  by default)**: ``EmbeddingOpportunityScorer`` (from P28) produces
  summary/pros/cons/ranking_explanation via fixed templates, which is
  functionally complete but reads mechanically.  This adds an optional
  enrichment pass that takes the already-computed structured output
  (relevance_score, required_skills, missing_skills — all correct and
  cheap) and makes exactly one short LLM call per opportunity to rewrite
  only the text fields into more natural prose.  If the call fails the
  template text is kept; the pipeline never breaks.
  - ``core/config/settings.py`` — ``narrative_enrichment_enabled: bool =
    Field(default=False)`` on ``AISettings`` (off by default since P28's
    purpose was removing the LLM dependency).  Configurable via
    ``OOS_AI__NARRATIVE_ENRICHMENT_ENABLED=true``.
  - **Enrichment prompt** provides the ALREADY-COMPUTED score, skills,
    title, and description, and asks only for natural summary/pros/cons/
    ranking_explanation text consistent with those given facts — the LLM
    is never asked to re-derive the score or skills.
  - **``score_opportunity``** (single-opportunity path): calls
    ``_enrich_single()`` which makes one ``generate_with_fallback`` call
    (reusing the existing OpenRouter→Groq→Gemini chain).  On parse
    failure or exception, logs a warning and returns ``None``; the caller
    keeps template text.
  - **``score_multiple_and_save``** (pipeline path): computes all
    template scores first, then calls ``_enrich_batch()`` which makes
    ONE LLM call for the entire batch (prompt includes all titles,
    scores, and skills).  Falls back to template text if the batch
    response cannot be parsed or the call raises.
  - **``score_and_save``**: enrichment path both updates the returned
    ``ScoredOpportunity`` and the ``Opportunity`` DB object.
  - Score, skills, and ``application_deadline`` are NEVER modified by
    enrichment — only summary, pros, cons, and ranking_explanation may
    be overwritten.
  - Tests: 21 new tests across ``TestParseEnrichmentResponse`` (7 cases:
    single valid/invalid/code-fence JSON, batch valid/wrong-type/missing-
    field), ``TestBuildEnrichmentBatchItems`` (single + multiple items),
    ``TestApplyEnrichment`` (overwrites text, preserves score/skills,
    None safe), and ``TestEnrichmentFlow`` (disabled-by-default never
    calls AI, enabled+succeeding overwrites text, enabled+failing
    exception falls back, enabled+bad-parse falls back, enriched
    ``score_and_save`` updates opportunity object, batch enrichment
    overwrites all items, batch failure falls back).

- **BackendManager — frontend now starts and owns the backend process**:
  The backend (uvicorn serving ``backend.main:app``) was previously
  started only via a manual dev script.  The frontend was auto-launched
  on Windows login (via ``frontend/utils/startup.py`` registering
  ``python -m frontend.main`` in ``HKCU\...\Run``) but the backend was
  never registered anywhere, so every API call failed on reboot and the
  entire daily-search-window + digest-email scheduling pipeline (owned by
  ``backend/main.py``'s ``lifespan()``) never ran unattended.  This was a
  fundamental bug — not cosmetic, the core automated pipeline was dead on
  any cold boot.
  - ``frontend/backend_manager.py`` — new ``BackendManager`` class:
    ``is_backend_healthy()`` does a quick ``GET /api/v1/health`` with a
    2-second timeout (no raise).  ``start_backend()`` spawns a detached
    ``uvicorn`` child process via ``subprocess.Popen`` with
    ``CREATE_NO_WINDOW`` on Windows and redirects stdout/stderr to
    ``{logs_dir}/backend.log`` for diagnostics.  ``ensure_backend_running()``
    checks health first (no spawn if already healthy), starts the backend
    if needed, then polls every 0.5 s for up to 15 s waiting for it to
    bind.  ``stop_backend()`` terminates gracefully (5s wait then kill)
    but only if *this instance* started the process — never kills a
    pre-existing manually-launched backend.
  - ``frontend/main.py`` startup: before constructing the ``MainWindow``,
    shows a frameless ``QSplashScreen``-style dialog with an indeterminate
    progress bar and "Starting OpportunityOS..." message, then calls
    ``ensure_backend_running()``.  If the backend fails to start within the
    timeout, a clean error dialog is shown with the log file path before
    proceeding into a degraded (offline) app state.
  - ``frontend/main.py`` shutdown: after ``app.exec()`` returns,
    ``manager.stop_backend()`` is called.  The tray's Quit action
    (``_on_quit`` → ``MainWindow.quit_application``) also calls
    ``app.quit()`` to actually exit the event loop (a pre-existing bug:
    ``setQuitOnLastWindowClosed(False)`` meant the Quit action closed the
    window but the process kept running).
  - Effect: the frontend is already registered for Windows auto-start; it
    now transitively brings up the backend too, every time — boot, manual
    launch, or post-crash restart.  The scheduler and digest pipeline are
    no longer silently dead on reboot.
  - Tests: ``tests/frontend/test_backend_manager.py`` — 17 tests covering
    health-check (200, 500, connection error, timeout), ``start_backend``
    (verifies command line, no double-spawn), ``ensure_backend_running``
    (already-healthy skips spawn, starts-and-returns-True, timeout-returns-
    False, process-exits-early-returns-False, process-not-leaked),
    ``stop_backend`` (non-owner untouched, already-exited no-op, graceful
    terminate, kill-after-timeout), and constructor (default/custom port).

- **Plugins now actually connected to the live search flow**: The 9 bundled
  finder plugins (internships, jobs, research_papers, grants, hackathons,
  conferences, competitions, startup_hiring, scholarships) were fully built
  with `pyproject.toml` entry points declared but were never discovered at
  runtime — nothing called `importlib.metadata.entry_points()` to load them.
  - `plugins/loader.py` — new module with `discover_entry_point_classes()`
    (uses `importlib.metadata.entry_points(group="opportunityos.plugins")`,
    falls back to the hardcoded `ALL_BUNDLED_PLUGINS` list when not installed
    editable) and `load_bundled_plugins(enabled_plugins)` which instantiates
    and initialises the filtered set.
  - `SearchExecutor` now loads plugin `SearchProvider` instances and runs
    each query through both the primary provider AND every enabled plugin's
    provider, collecting results with cross-provider URL dedup. This means
    every pipeline run automatically fetches domain-specialized results
    (internship listings, research papers, grants, etc.) alongside general
    job-board results.
  - `PipelineConfig` gains an `enabled_plugins: list[str] | None` field
    (default `None` = all discovered plugins active).
  - **Semantics**: empty `enabled_plugins` = all enabled (opt-out model for
    bundled first-party plugins). Set a non-empty list to restrict to specific
    plugins by `plugin_name`.

- **SearchExecutor now persists Search rows per query**: Each query run
  through the search provider during a pipeline execution creates a new
  `Search` row via `SearchRepository` with `query`, `user_id`,
  `result_count` (per-query, before cross-query dedup), and `last_run_at`.
  Failed queries still create a row with `result_count=0`. This populates
  the dashboard's `total_searches`, `today_searches`, and "Recent Searches"
  table. Event-log semantics — re-running the same query text creates a new
  row each time (correctly counting toward "today" on the day it runs).

- **P15 — Multi-profile support**: Users can now create up to 5 profiles
  (e.g. "R&D Track", "AI/ML Track") for different job search tracks.
  - `Profile` model: dropped `unique=True` on `user_id` (now one-to-many),
    added `name: str` field (default "Profile 1") as a user-given label,
    added non-unique index on `user_id`.
  - `Opportunity` model: added nullable `profile_id` FK to `profiles.id`
    for per-profile opportunity scoping going forward.
  - `ProfileRepository`: added `list_by_user_id()`, `count_by_user_id()`,
    and documented that `get_by_user_id()` now returns the oldest profile.
  - New endpoints:
    - `GET /users/{user_id}/profiles` — list all profiles for a user
    - `POST /profiles` — create profile (enforces 5-profile cap, 409 if exceeded)
    - `GET /profiles/id/{profile_id}` — fetch by profile id
    - `PUT /profiles/id/{profile_id}` — update by profile id
    - `DELETE /profiles/id/{profile_id}` — delete by profile id (blocks deleting last profile)
  - Deprecated but retained old `/profiles/{user_id}` routes for backward compat.
  - `POST /pipeline/run` now takes `profile_id` instead of `user_id` and
    resolves the profile directly; 404 if not found (no more auto-create-default).
  - `GET /opportunities` accepts optional `profile_id` filter.
  - `opportunity_creator.py` sets `profile_id` on new opportunities.
  - Tests: `tests/backend/test_profiles.py` covers 5-profile cap, listing,
    profile_id CRUD, last-profile deletion guard. `tests/database/test_profile_repository.py`
    covers new repo methods.

### Fixed

- **Migration 010 broken on fresh SQLite — unnamed UNIQUE constraint drop failed**:
  Migration `010_multi_profile.py` called
  `batch_op.drop_constraint("uq_profiles_user_id", type_="unique")` but the
  original constraint in migration 001 was created as
  `sa.UniqueConstraint("user_id")` with no explicit name. On SQLite this
  constraint has no stored name, so Alembic's batch mode could not find it
  by the guessed name and raised `ValueError`. Anyone cloning the repo fresh
  and running `alembic upgrade head` would hit this failure.
  - **Fix**: Added `naming_convention={"uq": "uq_%(table_name)s_%(column_0_N_name)s"}`
    to the `batch_alter_table` call for the `profiles` table. This is Alembic's
    documented pattern for dropping unnamed constraints on SQLite — the naming
    convention assigns a predictable name during reflection so that
    `drop_constraint` matches correctly. Also added `recreate="always"` for
    explicitness (SQLite already requires batch recreate, but this makes the
    intent clear).
  - Also moved the `opportunities` table changes (add `profile_id` column, FK,
    index) into a `batch_alter_table` context, since `op.create_foreign_key`
    fails on SQLite outside batch mode (`NotImplementedError: No support for
    ALTER of constraints in SQLite dialect`).
  - Both `upgrade()` and `downgrade()` now use `batch_alter_table` with
    `recreate="always"` for both `profiles` and `opportunities`.

- **Migration 005 downgrade failed — index not dropped before column**:
  `005_add_notification_fields.py:downgrade()` called
  `op.drop_column("notifications", "digest_id")` but the column had an
  associated index `ix_notifications_digest_id` (created by `index=True` in
  the upgrade). On SQLite, `ALTER TABLE ... DROP COLUMN` checks that no
  indexes reference the column; the operation failed with
  `OperationalError: error in index ix_notifications_digest_id after drop
  column: no such column: digest_id`. Fixed by adding
  `op.drop_index("ix_notifications_digest_id", table_name="notifications")`
  before the `drop_column` call. (Discovered by the new
  `test_migration_chain.py` test which runs the complete downgrade chain.)

- **`.env.example` drift — missing Notifications, Scheduler, Memory, Plugins vars**:
  `.env.example` was missing the entire Notifications section (`OOS_NOTIFICATIONS__*`),
  the Memory and Plugins sections, and about a dozen
  `OOS_BACKGROUND_SCHEDULER__*` vars (digest sub-task, pipeline tuning knobs,
  master switches). Also fixed `OOS_AI__OLLAMA__BASE_URL` → `OOS_AI__OLLAMA_BASE_URL`
  (double `__` would map to a non-existent `ai.ollama.base_url`). Full cross-check
  against `get_config()` usage confirmed no stale entries in the example file beyond
  the Ollama naming bug. See `.env.example` for the complete list.

### Removed

- **`scripts/fix_profile_unique.py` and `scripts/migrate_profile.py`** — these
  raw SQLite scripts were manual workarounds for the same migration 010 bug
  described above. With the fixed migration handling the constraint drop
  correctly end-to-end via Alembic batch mode, these scripts are no longer
  needed and have been deleted.

- **P14 — AI fallback chain: openrouter → groq → gemini → fail (no dummy/mock)**:
  Corrected the automatic fallback chain used by query generation and opportunity
  scoring. Previously the chain was hardcoded as `["groq", "openrouter"]` in two
  separate places (query_generator.py and scorer.py) with duplicated, buggy logic
  that reused the original provider's model name when switching to a fallback
  provider — breaking the fallback call itself. The fix:
  1. **`AIRegistry.default()`** now registers every real provider whose key/config
     is present (Gemini, OpenAI, Ollama, OpenRouter, Groq) instead of only
     OpenRouter and Groq. No dummy/mock provider is ever registered.
  2. **`AISettings.fallback_providers`** added to `core/config/settings.py` with
     default `["groq", "gemini"]`, making the full chain
     `openrouter (default_provider) → groq → gemini → fail`. Configurable via
     `OOS_AI__FALLBACK_PROVIDERS` (comma-separated or JSON array).
  3. **`services/ai/fallback.py`** — new shared `generate_with_fallback()` helper
     used by both query_generator.py and scorer.py, eliminating duplicated inline
     fallback logic. Critical fix: when calling a fallback provider, a fresh
     `ModelConfig` is built using that provider's own `default_model` property
     (added to `AIProvider` ABC and implemented on every provider class) instead
     of reusing the original model string.
  4. **`AIProvider.default_model`** abstract property added to the ABC and
     implemented on all five provider classes (Gemini: `gemini-2.0-flash`, Groq:
     `llama-3.3-70b-versatile`, OpenRouter: `meta-llama/llama-3.3-70b-instruct:free`,
     OpenAI: `gpt-4o-mini`, Ollama: `llama3.2`).
  5. **`backend/api/v1/endpoints/settings.py`** — removed the hardcoded `"dummyai"`
     entry from `_build_configuration_status()`; added `"groq"` to `_INTEGRATIONS`
     and `_is_configured()`.
  6. **Tests**: `tests/services/test_ai_fallback.py` covers primary-succeeds,
     primary-fails-groq-succeeds (with model verification), primary-and-groq-fail-
     gemini-succeeds, all-three-fail (with all error messages), no-openai/ollama/
     dummy attempted, deduplication, and unregistered-provider-skipped. Existing
     tests updated to mock `generate_with_fallback` instead of relying on the
     removed `dummyai` provider.

### Added

- **`tests/database/test_migration_chain.py` — full migration chain integration test**:
  Runs `alembic upgrade head` against a fresh temp SQLite database file from
  migration 001 all the way through 010, then `alembic downgrade base`, then
  `alembic upgrade head` again. Verifies the complete cycle succeeds and that
  migration 010's schema changes (no UNIQUE on profiles.user_id,
  `ix_profiles_user_id` index, `name` column, `profile_id` column on
  opportunities) are all present. This test would have caught the original
  migration 010 bug on fresh databases.

- **LaTeX resume parsing support**: `services/resume_parser/file_reader.py` now
  handles `.tex` files via new `read_tex()` function. Uses `pylatexenc` library
  for robust LaTeX-to-plain-text conversion — stripping preamble commands,
  formatting macros, comments, and environments while preserving section headers
  and bullet content. The `read_resume_file()` dispatcher now accepts `.tex`
  alongside `.pdf` and `.docx`. The `POST /api/v1/resume/parse` endpoint allows
  `.tex` uploads. Dependencies: `pylatexenc>=3.10` added to `pyproject.toml`.
   Tests: `tests/services/test_file_reader.py` covers `read_tex()` output quality
   and command stripping; `tests/backend/test_resume.py` covers end-to-end `.tex`
   parsing and section detection via the API.

- **P17 — Multi-profile frontend (switcher + form widget)**: The Profile page
  (`frontend/pages/profile.py`) was fully redesigned to support the multi-profile
  backend from P15/P16. Key changes:
  - **Profile switcher**: Horizontal scrollable card strip at page top showing up
    to 5 profile cards (name + subtitle derived from bio/skills/location). Each
    card has a delete (×) button with confirm-before-delete dialog. A "+ New
    Profile" card at the end of the strip is disabled with a tooltip when the
    user has reached 5 profiles.
  - **Empty state**: When the user has zero profiles, the page shows two large
    choice buttons — "Upload Resume" and "Fill Manually" — instead of an empty
    switcher strip.
  - **Choice dialog**: Clicking "+ New Profile" opens a clear two-button choice:
    "Upload Resume" (opens file picker restricted to .pdf/.docx/.tex, calls
    `POST /resume/parse`, pre-fills the form for review before saving) vs "Fill
    Manually" (opens an empty form, user fills and saves).
  - **ProfileForm widget** (`frontend/widgets/profile_form.py`): New reusable
    form widget covering every `Profile` model field: name (profile label),
    display_name, bio, education (repeatable rows), experience (repeatable rows),
    projects (repeatable rows), skills (tag/chip input), preferred_locations,
    salary_expectations, target_companies, keywords, linkedin_url, github_url,
    portfolio. Used for both create (`POST /profiles`) and edit (`PUT
    /profiles/id/{profile_id}`) modes. An `on_saved` callback notifies the
    page to refresh the profile list after a successful save.
  - **Profile selection**: Clicking an existing profile card loads it into the
    form in edit mode. Active profile is highlighted with a left accent border.
  - Tests: `tests/frontend/test_profile_page.py` covers form structure,
    populate/collect/clear, new-profile-card limit gating (disabled at 5),
    empty state visibility, switcher rendering with profiles, profile selection,
    profile deletion from list, and upload-resume parse-then-fill flow.

- **P13 — UI for manual digest trigger and email testing**: Added two new buttons to
  the Notifications page (`frontend/pages/notifications.py`):
  1. **"Send Digest Now"** button (green): Calls `POST /notifications/digest/trigger`
     and displays a toast/label with the result (e.g., "Digest sent — 4 items" or
     "No new notifications to send"). On success, auto-refreshes the notification
     list after 3 seconds so users see new in-app notifications immediately.
  2. **"Test Email"** button (amber): Prompts for an email address via input dialog
     and calls `POST /notifications/test-email` with that address. Displays success/failure
     feedback in the header label, allowing users to verify SMTP configuration works
     without waiting for a scheduled digest cycle.
  - Full test coverage in `tests/frontend/test_notifications_page.py`.
  - Buttons are styled consistently with existing page buttons and include hover effects.
  - Tests use mocking to avoid requiring a display server; integration tests can be
    run manually on a development machine with PyQt6/PySide6 available.

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

- **P12 — Notifications pipeline was never persisting to database**: `NotifierStep`
  (`services/search_pipeline/steps/notifier.py`) was only emitting console log
  events via `LoggingNotifier` and never actually calling `NotificationService`
  to persist `Notification` DB rows. This caused the digest email to find zero
  unread notifications and never send anything. Fixed by:
  1. Modified `NotifierStep` to accept a `db: Session` parameter (same pattern
     as `OpportunityCreator`) and use `NotificationService` to create DB records
     for each scored opportunity above a threshold (default: score >= 50/100), capped
     at 10 per pipeline run to prevent user notification flooding.
  2. Always creates a `type_="pipeline_run"` summary notification even if no
     individual opportunities meet the threshold, so users see pipeline activity.
  3. Fixed email-send gating bug in `DailyDigestService.run()`: the `if self._email
     and user_email and self._settings.include_unread_only:` condition was treating
     `include_unread_only` (a digest *content* filter) as an email *send* toggle;
     changed to `if self._email and user_email:` so email now sends regardless of
     that setting. The setting still correctly filters which notifications are
     *queried* for digest content (unread-only vs. all).
  4. Enhanced `DailyDigestService._build_summary()` to render opportunity
     notifications with score and URL from metadata (e.g., "Research Intern
     (score 87/100) https://example.com/job") instead of bare titles, making
     digests actionable without requiring users to view in-app notifications.
- **BUG: OpenRouter provider using fake/unverified models**: The OpenRouter
  provider was using a non-existent default model ID (`"openrouter/free"`,
  which has no direct equivalent on OpenRouter's API) and a hardcoded
  `supported_models` list containing model IDs that do not exist or are not
  available as free-tier options on the platform (e.g. `"openai/gpt-4o:free"`,
  `"anthropic/claude-3.5-sonnet:free"`, `"google/gemini-2.0-flash:free"`).
  Fixed by:
  1. Changing the default model to `"meta-llama/llama-3.3-70b-instruct:free"`,
     a confirmed real and available free model on OpenRouter.
  2. Replacing the hardcoded static list with a live-fetch mechanism
     (`_fetch_free_models()`) that queries OpenRouter's `/models` API endpoint,
     filters for models ending in `:free`, and caches the result for 1 hour.
     `supported_models` is now an `async` method (instead of a sync `@property`)
     that delegates to `_fetch_free_models()`. The `AIProvider` ABC and all
     six concrete provider classes (OpenRouter, Gemini, Groq, OpenAI, Ollama,
     Dummy) were updated to make `supported_models` an `async def` method.
     `AIRegistry.models()` is also `async` now, and the `GET /ai/providers`
     endpoint awaits it.
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
