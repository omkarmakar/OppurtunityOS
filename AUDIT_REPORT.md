# P20 — Full Application Sanity Audit

**Date:** 2026-07-26  
**Scope:** OpportunityOS entire codebase  
**Method:** Read-only investigation, migration replay, schema diff, sub-agent analysis, test suite execution  
**Policy:** No fixes applied (except trivial docstring typos); all findings documented for targeted fix-prompts.

---

## 1. Alembic Migration Chain Integrity

**Status: ⚠️ Issues found**

- **10 migration versions** (`001`–`010`), linear chain, no branches:
  `001→002→003→004→005→006→007→008→009→010`
- All versions have correct `down_revision` pointers.
- Chain walked and confirmed no gaps or forks.

### Critical: Migration `010_multi_profile.py` fails on fresh SQLite

- **Problem:** Line 28 calls `batch_op.drop_constraint("uq_profiles_user_id", type_="unique")` inside `op.batch_alter_table("profiles")`. SQLite auto-generates unnamed UNIQUE constraints via `CREATE UNIQUE INDEX` in the sqlite_master table — the name `"uq_profiles_user_id"` **never existed** for the original UNIQUE on `profiles.user_id` (created in migration `002` via `sa.UniqueConstraint("user_id", name="uq_profiles_user_id")` within a `CreateTable` that SQLite ignores for naming).
- **Result:** Alembic throws `"No such constraint: uq_profiles_user_id"` on a fresh DB replay.
- **Impact:** Anyone cloning the repo and running `alembic upgrade head` on a fresh SQLite DB gets a broken migration. Existing databases that have already run 001→009 will work since the constraint name is only checked during DDL.
- **`downgrade()`** (lines 55–65) has the parallel issue: `batch_op.create_unique_constraint("uq_profiles_user_id", ["user_id"])` in downgrade will also fail on SQLite because `create_unique_constraint` doesn't actually emit DDL in SQLite batch mode.

### Minor: `op.batch_alter_table` used inconsistently

- Migration 010 uses `batch_alter_table` for `profiles` changes but direct `op.add_column`/`op.create_foreign_key`/`op.create_index` for `opportunities` changes. While not incorrect (both work), it's inconsistent and could confuse maintainers.

---

## 2. Database Referential Integrity

**Status: ⚠️ Issues found**

### Missing `PRAGMA foreign_keys=ON`

- **`database/session.py:37-41`** — `sessionmaker` is created without setting `PRAGMA foreign_keys=ON`.
- SQLite **defaults to foreign_keys=OFF**, so every FK constraint declared in the models is **decorative only** during runtime.
- **Confirmed via test:** Inserting orphan `user_id` values into `profiles`, `notifications`, `opportunities`, etc. succeeds silently.
- **Impact:** Data corruption is possible (e.g., deleting a user leaves orphan rows in 8+ child tables). The app relies entirely on application-level integrity.

### All 10 models have FK relationships, all unenforced at DB level (on SQLite):

| Model | FK to | Cascade | Enforced? |
|---|---|---|---|
| Profile | users.id | CASCADE | No |
| Notification | users.id | CASCADE | No |
| Opportunity | profiles.id (010) | SET NULL | No |
| Opportunity | users.id | CASCADE | No |
| Bookmark | users.id | CASCADE | No |
| Bookmark | opportunities.id | CASCADE | No |
| PipelineRun | profiles.id | CASCADE | No |
| Source | opportunities.id | CASCADE | No |
| Search | profiles.id | CASCADE | No |
| SchedulerState | users.id | CASCADE | No |

### All 10 models have corresponding repositories, no orphan models:

| Model | Repository | File |
|---|---|---|
| ApplicationSettings | ApplicationSettingsRepository | `repositories/application_settings_repository.py` |
| Bookmark | BookmarkRepository | `repositories/bookmark_repository.py` |
| Notification | NotificationRepository | `repositories/notification_repository.py` |
| Opportunity | OpportunityRepository | `repositories/opportunity_repository.py` |
| PipelineRun | PipelineRunRepository | `repositories/pipeline_run_repository.py` |
| Profile | ProfileRepository | `repositories/profile_repository.py` |
| SchedulerState | SchedulerStateRepository | `repositories/scheduler_state_repository.py` |
| Search | SearchRepository | `repositories/search_repository.py` |
| Source | SourceRepository | `repositories/source_repository.py` |
| User | UserRepository | `repositories/user_repository.py` |

---

## 3. Pipeline & Search Logic

**Status: ✅ No issues found**

### Pipeline `ctx` dict flow (sub-agent audit)

- All 6 steps (`SearchExecutor`, `ContentExtractor`, `ScoringStep`, `DeduplicatorStep`, `FilterStep`, `NotifierStep`) read/write consistent keys in the `ctx` dict.
- Naming and shape of intermediate artifacts (`search_results`, `extracted_contents`, `opportunities`, etc.) is consistent across all steps.
- No `.get(key, default)` calls that silently mask missing keys.
- `ctx` dict is initialized per-run in `SearchPipeline.run()` and flows through each step.
- Cross-query dedup in `DeduplicatorStep` operates on the accumulated `opportunities` list after all queries for a provider are processed.

### SearchExecutor (verified after P19 fix)

- One `Search` row created per query via `SearchRepository`, with per-query `result_count` captured before cross-query dedup.
- Failed queries get `result_count=0`.
- `result_count` is populated from the search provider response length, not inferred.
- No regression in pipeline test suite.

### AI fallback chain

- Clean: `primary → fallback → dummy` — no dangling retry loops.
- `AIRegistry` properly degrades through provider list.
- `DummyProvider` is always available as last resort.

---

## 4. AI Provider Configuration

**Status: ✅ No issues found**

- 5 AI providers configured: `OpenAI`, `Gemini`, `Groq`, `Ollama`, `OpenRouter`.
- `DummyProvider` always available.
- Provider selection via `config.ai.default_provider` string key.
- API keys from env vars (`OOS_AI__*_API_KEY`) mapped correctly in `settings.py`.
- Fallback chain in `AIRegistry.get_provider()`: requested → fallback list → dummy.
- No credential leakage in logs (keys redacted via `SecretStr` in config model).
- All providers return `AIResponse` dataclass — consistent interface.

---

## 5. Notification & Digest System

**Status: ✅ No issues found**

### Components

| Component | File | Role |
|---|---|---|
| `Notification` model | `models/notifications.py` | DB row per notification |
| `NotificationRepository` | `repositories/notification_repository.py` | CRUD + unread queries |
| `NotificationService` | `notifications/service.py` | Orchestrator: create + deliver |
| `DesktopNotificationProvider` | `notifications/providers.py` | Desktop toast delivery |
| `EmailNotificationProvider` | `notifications/providers.py` | SMTP email delivery |
| `DailyDigestService` | `notifications/digest.py` | Aggregates unread → digest notification |
| `NotificationScheduler` | `notifications/scheduler.py` | Polling thread for digest dispatch |

### Flow

1. `NotifierStep` (pipeline) calls `NotificationService.create_notification()` for each new opportunity.
2. `NotificationService` persists to `Notification` table, optionally delivers via Desktop/Email provider.
3. `DailyDigestService` collects unread `in_app` notifications, builds summary, creates a "digest" notification, optionally emails it.
4. `BackgroundScheduler` via `tasks.py:_digest_callback()` triggers `DailyDigestService.run()` on interval.
5. Frontend polls `GET /api/v1/notifications/unread/count` for badge display.

### No gaps found

- Channel routing (`in_app`, `desktop`, `email`) is correctly implemented.
- `digest_id` linking between individual notifications and digest summary is correct.
- Email config (SMTP host/port/auth) is read from config, properly conditional on `email_enabled`.
- Desktop notifications skip if provider not initialized.

---

## 6. Background Scheduler

**Status: ⚠️ Minor issue found**

### Architecture

- `BackgroundScheduler` (`services/background/scheduler.py`) — daemon-thread polling scheduler.
- `ScheduledTask` dataclass — name, interval, callback, retry config, optional `run_condition`.
- `tasks.py` — factory `create_and_start_scheduler()` registers two tasks: `pipeline` (windowed) and `digest` (interval-based).
- `SchedulerState` model/repo tracks `last_run_date` per user+task for the window condition.

### Minor: Pipeline task interval mismatch in registration

- **`tasks.py:200`** — pipeline `ScheduledTask` is created with `interval_seconds=60` and the comment says "no-op placeholder since run_condition takes over due-checking".
- The `_tick()` logic at `scheduler.py:122-124` checks `run_condition` first and skips the interval check if present, so this is **functionally correct**.
- However, setting `interval_seconds=60` while the actual window is hours-long is misleading. A value of `0` or a clarifying comment would be clearer.

### Pipeline window-miss log is best-effort

- `tasks.py:173-196` — checks if the pipeline window was missed on startup and logs it. The logic compares `local_hour >= pipeline_window_end_hour` against the state. This is purely informational and has no effect on behavior. No issue.

### Test coverage

- `test_background_scheduler.py` — 8 tests covering start/stop, idempotent start, clamping, task add/remove, tick logic, retry, concurrent skip.
- `test_thread_safety.py` — 3 tests covering concurrent add/remove, concurrent tick.
- Coverage is adequate.

---

## 7. Frontend–Backend Contract Alignment

**Status: ✅ No issues found (sub-agent audit)**

### Endpoints audited (20+ endpoints across 13 router files)

- **Health** (`GET /api/v1/health`) — returns `{status, database, version}` — matches frontend startup check in `main_window.py`.
- **Version** (`GET /api/v1/version`) — returns `{name, version, python}` — matches frontend display.
- **Profiles** (`GET/PUT /api/v1/profiles/me`) — returns `Profile` schema — frontend reads `name`, `skills`, `experience`, etc.
- **Users** (`POST /api/v1/users`, `GET /api/v1/users/me`) — matches frontend auth flow.
- **Opportunities** (`GET/POST /api/v1/opportunities`, `GET /api/v1/opportunities/{id}`) — frontend calls with expected filters (`source`, `type`, `score_min`, `date_from`, etc.).
- **Bookmarks** (`POST/DELETE /api/v1/bookmarks`, `GET /api/v1/bookmarks`) — CRUD matches frontend toggle.
- **Notifications** (`GET /api/v1/notifications`, `POST /api/v1/notifications/{id}/read`, `GET .../unread/count`) — frontend polls count, marks read.
- **Search** (`POST /api/v1/search`, `GET /api/v1/search/history`) — matches pipeline trigger + history view.
- **Dashboard** (`GET /api/v1/dashboard/stats`) — frontend expects `{total_opportunities, new_today, active_sources, ...}`.
- **Settings** (`GET/PUT /api/v1/settings`, `GET /api/v1/settings/app`) — frontend reads/writes user preferences.
- **Content** (`GET /api/v1/content/{url}`) — frontend calls for scraped content display.
- **AI** (`POST /api/v1/ai/chat`, `POST /api/v1/ai/summarize`) — frontend chat widget matches.
- **Resume** (`POST /api/v1/resume/parse`, `GET /api/v1/resume`) — frontend upload flow matches.

### Schema drift check

- All Pydantic response models in `backend/api/v1/schemas/` are consistent with what frontend `httpx` calls expect.
- No extraneous fields returned by backend that frontend ignores (or vice versa).
- `user_id` vs `profile_id` distinction is correctly handled: frontend operations target the active profile, backend resolves profile→user internally.

### Pagination

- All `list` endpoints accept `limit`/`offset` query params; frontend passes them.
- Frontend scroll/pagination logic respects the `limit` parameter.

---

## 8. Environment & Configuration

**Status: ⚠️ Minor gaps found**

### Config sources

| Source | Format | Priority |
|---|---|---|
| `config/default.yaml` | YAML | Base/defaults |
| `config/{environment}.yaml` | YAML | Environment override (deep-merge) |
| Environment vars | `OOS_{SECTION}__{KEY}` | Highest priority |

### Config model (`core/config/settings.py`)

- `AppConfig` Pydantic model with nested sections: `database`, `server`, `logging`, `paths`, `plugins`, `notifications`, `ai`, `background_scheduler`.
- `BackgroundSchedulerSettings` — 14 fields covering pipeline window, digest interval, timezone, retry, etc.
- `DigestSettings` — 5 fields covering max opportunities, interval, retry.
- `NotificationSettings` — email SMTP config, desktop toggle, digest settings nested.

### `.env.example` gaps

| Setting defined in `settings.py` | Present in `.env.example`? |
|---|---|
| `OOS_DATABASE__*` | ✅ Yes |
| `OOS_LOGGING__*` | ✅ Yes |
| `OOS_SERVER__*` | ✅ Yes |
| `OOS_PATHS__*` | ✅ Yes |
| `OOS_TAVILY__*` | ✅ Yes |
| `OOS_AI__*` | ✅ Yes |
| `OOS_BRAVE_SEARCH__*` | ✅ Yes (legacy, marked as discontinued) |
| `OOS_BACKGROUND_SCHEDULER__*` | ✅ Some (pipeline_search_provider, timezone, window hours) |
| `OOS_NOTIFICATIONS__*` | ❌ **Missing** — no email SMTP vars documented |
| `OOS_BACKGROUND_SCHEDULER__DIGEST_ENABLED` | ❌ **Missing** |
| `OOS_BACKGROUND_SCHEDULER__DIGEST_INTERVAL_SECONDS` | ❌ **Missing** |
| `OOS_AI__GROQ__*` | ❌ **Missing** (Groq has its own config section in `settings.py`) |

### `default.yaml` gaps

- Does not include `background_scheduler`, `notifications`, or `ai` sections — these only exist in env vars and config model defaults.
- This means the config model defaults are the effective fallback, but there's no single source of truth YAML that documents all possible config keys.

---

## 9. Plugin Architecture

**Status: ✅ No issues found**

### Bundled plugins (9)

| Plugin | Domain | Tested? |
|---|---|---|
| CompetitionFinderPlugin | competitions | ✅ `test_bundled.py` |
| ConferenceFinderPlugin | conferences | ✅ |
| GrantFinderPlugin | grants | ✅ |
| HackathonFinderPlugin | hackathons | ✅ |
| InternshipFinderPlugin | internships | ✅ |
| JobFinderPlugin | jobs | ✅ |
| ResearchPaperFinderPlugin | research_papers | ✅ |
| ScholarshipFinderPlugin | scholarships | ✅ |
| StartupHiringFinderPlugin | startup_hiring | ✅ |

- All 9 plugins tested via parametrized `test_bundled.py` (11 tests × 9 plugins = 99 test cases).
- Each plugin defines `plugin_name`, `plugin_version`, `plugin_description`, `plugin_author`.
- Each plugin registers exactly one `SearchProvider`.
- `ALL_BUNDLED_PLUGINS` list in `plugins/bundled/__init__.py` matches all 9.
- Entry point group `opportunityos.plugins` is registered (verified via `importlib.metadata`).
- `_domain` and `_keywords` metadata is defined on each provider's SearchProvider class.
- Wrapping pattern (`DomainProvider(inner=DummyProvider())`) is consistent.

---

## 10. Test Suite Health

**Status: ⚠️ Issues found**

### Test discovery

- **51 test files** total across `tests/backend/` (16), `tests/core/` (1), `tests/database/` (4), `tests/frontend/` (7), `tests/plugins/` (1), `tests/services/` (17).
- Frontend tests (7 files) require a Qt display server and **hang** on headless CI (e.g., GitHub Actions Windows runner, WSL). These must be excluded or marked `@pytest.mark.skipif`.
- Backend API tests (16 files) depend on `TestClient` fixture that creates an in-memory SQLite DB — these run correctly in isolation.

### Test results (backend/core/database/services only — frontend excluded)

**All tests passing** in the following modules:
- `tests/backend/test_health.py` (3/3)
- `tests/backend/test_version.py` (5/5)
- `tests/backend/test_users.py`
- `tests/backend/test_profiles.py`
- `tests/backend/test_opportunities.py`
- `tests/backend/test_notifications.py`
- `tests/backend/test_bookmarks.py`
- `tests/backend/test_search_providers.py`
- `tests/backend/test_settings.py`
- `tests/backend/test_settings_redaction.py`
- `tests/backend/test_rate_limit.py`
- `tests/backend/test_scoring.py`
- `tests/backend/test_resume.py`
- `tests/backend/test_content.py`
- `tests/backend/test_ai.py`
- `tests/backend/test_dashboard.py`
- `tests/backend/test_pipe.py`
- `tests/backend/test_user_settings.py`
- `tests/core/test_config.py`
- `tests/database/test_models.py`
- `tests/database/test_session.py`
- `tests/database/test_repositories.py`
- `tests/database/test_profile_repository.py`
- `tests/database/test_user_repository.py`
- `tests/services/test_*.py` (17 files)

### Test quality observations

- **Good:** Parametrized tests used effectively in `test_bundled.py`, `test_search_providers.py`, `test_search_pipeline.py`.
- **Good:** Async test support via `@pytest.mark.asyncio` and `pytest-asyncio` plugin.
- **Good:** Repository tests use an in-memory SQLite DB with table creation per test class.
- **Good:** Service tests mock external dependencies (HTTP calls, file system, email SMTP).

### Coverage gaps

- No integration test that runs the full migration chain from 001→010 on a fresh SQLite DB (would have caught the migration 010 bug).
- No test that verifies FK enforcement (or lack thereof).
- No test for the config model's environment variable parsing (env var → `AppConfig`).
- Frontend tests are non-functional on headless systems without explicit workaround.

---

## 11. Dead Code Analysis

**Status: ✅ No significant dead code found**

### Checked:
- **All exported symbols** in `services/__init__.py` — all 20+ symbols are referenced elsewhere in the codebase.
- **All 9 bundled plugins** — all referenced in `ALL_BUNDLED_PLUGINS` and tested.
- **All 10 models** — all have corresponding repositories, all models are imported in `database/models/__init__.py`.
- **All 10 repositories** — all imported in `repositories/__init__.py`, all used in at least one service or task.
- **Migration files** — all 10 versions are connected in the chain; no orphan versions.
- **Config model** — all settings fields are used by at least one service or endpoint.

### Potential orphan items (low confidence — may be used dynamically):
- `services/base.py` — `BaseService` class: referenced in `services/__init__.py` but no subclass imports found in search. Exported but possibly unused.
- `plugins/bundled/_base.py` — `BundledSearchProvider` base class: used by all 9 bundled plugin providers. Not dead code — actively used as base class.
- `database/repositories/base.py` — `BaseRepository`: used by all 10 repository classes. Not dead code.

---

## 12. Summary & Top-10 Findings

### Critical (blocking correctness)

| # | Finding | Severity | File | Suggested Fix |
|---|---|---|---|---|
| 1 | **Migration 010 fails on fresh SQLite** | Critical | `010_multi_profile.py:28` | Replace `drop_constraint("uq_profiles_user_id")` with batch-compatible SQLite approach; skip named constraint operations |
| 2 | **No `PRAGMA foreign_keys=ON`** | Critical | `session.py:37-41` | Add `cursor.execute("PRAGMA foreign_keys=ON")` after engine connect, or use `@event.listens_for(engine, "connect")` |
| 3 | **FK constraints unenforced on SQLite** | Critical | All model files | Application must rely on application-level integrity; foreign keys are decorative without PRAGMA |

### High (maintainability / completeness)

| # | Finding | Severity | File | Suggested Fix |
|---|---|---|---|---|
| 4 | **`.env.example` missing notification & digest settings** | High | `.env.example:58-61` | Add `OOS_NOTIFICATIONS__*` vars, `OOS_BACKGROUND_SCHEDULER__DIGEST_*` vars, `OOS_AI__GROQ__*` vars |
| 5 | **`default.yaml` missing `background_scheduler`, `notifications`, `ai` sections** | High | `config/default.yaml` | Add documented defaults for all config sections to serve as single source of truth |
| 6 | **Frontend tests hang on headless/CI** | High | `tests/frontend/*` | Mark all Qt-dependent tests with `@pytest.mark.skipif(not os.environ.get("DISPLAY") and platform.system() != "Windows")` |
| 7 | **Pipeline task `interval_seconds=60` is misleading** | Medium | `tasks.py:200` | Change to `interval_seconds=0` or add explicit clarifying comment |

### Medium (best practices)

| # | Finding | Severity | File | Suggested Fix |
|---|---|---|---|---|
| 8 | **`BaseService` exported but unused** | Low | `services/base.py` | Confirm intent; if truly unused, remove from exports |
| 9 | **No integration test for full migration chain** | Medium | N/A | Add a test that runs `alembic upgrade head` on a fresh temp SQLite DB to catch future migration breaks |
| 10 | **Migration 010 uses inconsistent batch/non-batch pattern** | Low | `010_multi_profile.py:36-52` | Use consistent approach (both batch or both direct) for clarity |

### End-to-End Assessment

**Overall health: Moderate.** The core business logic (pipeline, search, scoring, notifications, plugins) is well-architected, well-tested, and has no logic bugs. The two critical issues — a broken migration on fresh SQLite and completely decorative FK constraints — are database-layer problems that only manifest on SQLite (the default/only supported DB). These are straightforward to fix but represent real data-integrity risks in production. The config documentation gaps are minor but would cause confusion for new contributors. The test suite is strong overall, with the frontend-headless issue being the main CI blocker.
