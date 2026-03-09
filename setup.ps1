# ============================================================
# InvestZA - Windows PowerShell Setup Script
# Run: .\setup.ps1
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========== InvestZA Platform Setup ==========" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python
Write-Host "Checking Python..." -ForegroundColor Yellow

try {
    $pythonVersion = python --version
    Write-Host "Python detected: $pythonVersion" -ForegroundColor Green
}
catch {
    Write-Host "Python is not installed. Install from https://python.org" -ForegroundColor Red
    exit
}

# 2. Create virtual environment
Write-Host ""
Write-Host "Creating virtual environment..." -ForegroundColor Yellow

if (Test-Path "venv") {
    Write-Host "Virtual environment already exists" -ForegroundColor Green
}
else {
    python -m venv venv
    Write-Host "Virtual environment created" -ForegroundColor Green
}

# 3. Activate environment
Write-Host ""
Write-Host "Activating virtual environment..." -ForegroundColor Yellow

& ".\venv\Scripts\Activate.ps1"

# 4. Upgrade pip
Write-Host ""
Write-Host "Upgrading pip..." -ForegroundColor Yellow

python -m pip install --upgrade pip

# 5. Install dependencies
Write-Host ""
Write-Host "Installing requirements..." -ForegroundColor Yellow

pip install -r requirements.txt

# 6. Setup environment file
Write-Host ""
Write-Host "Checking .env file..." -ForegroundColor Yellow

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env file created" -ForegroundColor Green
}
else {
    Write-Host ".env already exists" -ForegroundColor Green
}

# 7. Run migrations
Write-Host ""
Write-Host "Running migrations..." -ForegroundColor Yellow

python manage.py makemigrations
python manage.py migrate

# 8. Collect static
Write-Host ""
Write-Host "Collecting static files..." -ForegroundColor Yellow

python manage.py collectstatic --noinput

# 9. Load seed data
Write-Host ""
Write-Host "Loading seed data..." -ForegroundColor Yellow

python manage.py loaddata fixtures/initial_data.json

# 10. Create admin
Write-Host ""
Write-Host "Create Django admin account" -ForegroundColor Yellow

python manage.py createsuperuser

Write-Host ""
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host ""

Write-Host "Run the server with:" -ForegroundColor Cyan
Write-Host "python manage.py runserver"
Write-Host ""