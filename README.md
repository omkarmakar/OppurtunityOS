# OpportunityOS

A modular desktop application platform built with Python, FastAPI, and PySide6.

## Architecture

```
OpportunityOS/
├── backend/        # FastAPI REST API
├── frontend/       # PySide6 GUI application
├── core/           # Shared domain library (config, logging, exceptions)
├── database/       # SQLAlchemy ORM + Alembic migrations
├── services/       # Business logic services
├── plugins/        # Plugin system
├── config/         # YAML configuration files
├── assets/         # Icons and resources
├── tests/          # Test suite
├── docs/           # Documentation
└── scripts/        # Development scripts
```

## Configuration System

Three-tier loading (lowest to highest precedence):

1. **YAML defaults** — `config/default.yaml`
2. **Environment overrides** — `config/{environment}.yaml` (deep-merged)
3. **Environment variables** — `OOS_*` prefixed vars / `.env` file

### Usage

```python
from core.config import get_config, ConfigurationProvider

cfg = get_config()
cfg.database.url           # "sqlite:///./data/opportunity.db"
cfg.server.port            # 8000
cfg.logging.level          # "DEBUG"
cfg.environment            # "development"

# Dependency injection
provider = ConfigurationProvider()
provider.config.paths.data_dir  # "data"

# Testing — switch environment
from core.config import reload_config
cfg = reload_config(environment="testing")
```

### Environments

| File                    | Environment    |
|-------------------------|----------------|
| `config/default.yaml`   | Base values    |
| `config/development.yaml` | Development  |
| `config/testing.yaml`   | Testing        |
| `config/production.yaml`| Production     |

## Database Layer

### Models

8 ORM entities with UUID primary keys, server-default timestamps, and relationship integrity:

| Model                | Table                | Key Relationships                  |
|----------------------|----------------------|------------------------------------|
| `User`               | `users`              | → Profile, Source, Search          |
| `Profile`            | `profiles`           | User (cascade delete)              |
| `Source`             | `sources`            | User, Opportunity                  |
| `Search`             | `searches`           | User, Opportunity (M2M)            |
| `Opportunity`        | `opportunities`      | Source, Search (M2M), Bookmark     |
| `Bookmark`           | `bookmarks`          | User, Opportunity                  |
| `Notification`       | `notifications`      | User                               |
| `ApplicationSettings`| `application_settings`| User (unique)                     |

### Repository Pattern

```python
from database.repositories import UserRepository
from database import SessionLocal

repo = UserRepository(SessionLocal())

user = repo.get(user_id)          # by primary key
users = repo.list()               # all
users = repo.list(email="...")    # with filter
repo.add(new_user)                # insert
repo.update(user, name="New")     # partial update
repo.delete(user_id)              # delete
cnt = repo.count()                # total
cnt = repo.count(is_verified=True) # filtered count
exists = repo.exists(user_id)    # boolean
```

### Migrations

```powershell
cd database
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Tests

47 database tests (table schema, model CRUD, relationships, constraints, timestamps, repository operations):

```powershell
uv run pytest tests/database/ -v
```

### Environment Variables

```ini
OOS_ENVIRONMENT=development
OOS_DATABASE__URL=sqlite:///./data/opportunity.db
OOS_DATABASE__ECHO=false
OOS_DATABASE__POOL_SIZE=5
OOS_LOGGING__LEVEL=DEBUG
OOS_SERVER__HOST=127.0.0.1
OOS_SERVER__PORT=8000
OOS_SECRET_KEY=change-me-in-production
```

Nested settings use `__` as delimiter. Copy `.env.example` → `.env` to get started.

## Prerequisites

- Python 3.13+
- uv (Python package manager)

## Setup

```powershell
# Clone the repository
git clone <repo-url> OpportunityOS
cd OpportunityOS

# Run setup script
.\scripts\setup.ps1
```

## Running

```powershell
# Backend
.\scripts\run.ps1 backend

# Frontend
.\scripts\run.ps1 frontend

# Tests
.\scripts\run.ps1 tests

# Lint
.\scripts\run.ps1 lint
```

## Tech Stack

| Component     | Technology     |
|---------------|----------------|
| Backend       | FastAPI        |
| GUI           | PySide6        |
| ORM           | SQLAlchemy     |
| Migrations    | Alembic        |
| Logging       | Loguru         |
| Validation    | Pydantic       |
| Config        | YAML + .env    |
| Tests         | Pytest         |
| Linting       | Ruff           |
| Formatting    | Black          |
| Dependencies  | uv             |
