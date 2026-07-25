# Run scripts for OpportunityOS
param(
    [ValidateSet("backend", "frontend", "tests", "lint")]
    [string]$Target = "backend"
)

switch ($Target) {
    "backend" {
        Write-Host "Starting backend server..." -ForegroundColor Cyan
        uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
    }
    "frontend" {
        Write-Host "Starting frontend application..." -ForegroundColor Cyan
        uv run python -m frontend.main
    }
    "tests" {
        Write-Host "Running tests..." -ForegroundColor Cyan
        uv run pytest
    }
    "lint" {
        Write-Host "Running linters..." -ForegroundColor Cyan
        uv run ruff check .
        uv run black --check .
    }
}
