# Setup script for OpportunityOS development environment
param(
    [string]$PythonVersion = "3.13"
)

Write-Host "Setting up OpportunityOS development environment..." -ForegroundColor Cyan

# Verify Python version
$python = (Get-Command python).Source
$version = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "Python $version detected at $python" -ForegroundColor Green

# Install uv if not present
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv package manager..." -ForegroundColor Yellow
    pip install uv
}

# Create virtual environment and install dependencies
Write-Host "Creating virtual environment and installing dependencies..." -ForegroundColor Yellow
uv venv
uv pip install -e ".[dev]"

# Create data directory
New-Item -ItemType Directory -Path "data" -Force | Out-Null

Write-Host "Setup complete!" -ForegroundColor Green
