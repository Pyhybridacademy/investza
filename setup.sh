#!/bin/bash
# ============================================================
# InvestZA - Automated Setup Script
# Run this once after cloning the project
# ============================================================

set -e

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║         InvestZA - Platform Setup Script         ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ─── 1. Check Python ──────────────────────────────────────
echo "→ Checking Python version..."
python3 --version || { echo "ERROR: Python 3 not found."; exit 1; }

# ─── 2. Create virtual environment ────────────────────────
echo ""
echo "→ Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate
echo "  ✓ Virtual environment activated"

# ─── 3. Upgrade pip ───────────────────────────────────────
echo ""
echo "→ Upgrading pip..."
pip install --upgrade pip -q

# ─── 4. Install dependencies ──────────────────────────────
echo ""
echo "→ Installing dependencies from requirements.txt..."
pip install -r requirements.txt
echo "  ✓ All dependencies installed"

# ─── 5. Environment file ──────────────────────────────────
echo ""
echo "→ Setting up environment configuration..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  ✓ .env file created from template"
    echo "  ⚠  Please edit .env and set your SECRET_KEY and other values!"
else
    echo "  ✓ .env already exists"
fi

# ─── 6. Database migrations ───────────────────────────────
echo ""
echo "→ Running database migrations..."
python manage.py makemigrations accounts
python manage.py makemigrations investments
python manage.py makemigrations deposits
python manage.py makemigrations withdrawals
python manage.py makemigrations administration
python manage.py migrate
echo "  ✓ Database migrations complete"

# ─── 7. Static files ──────────────────────────────────────
echo ""
echo "→ Collecting static files..."
python manage.py collectstatic --noinput
echo "  ✓ Static files collected"

# ─── 8. Create superuser ──────────────────────────────────
echo ""
echo "→ Creating admin superuser..."
python manage.py createsuperuser --email admin@investza.co.za || echo "  (Superuser may already exist)"

# ─── 9. Load initial data ─────────────────────────────────
echo ""
echo "→ Loading initial seed data..."
python manage.py loaddata fixtures/initial_data.json 2>/dev/null || echo "  (No fixtures found - skipping)"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║              Setup Complete! 🎉                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "→ To start the development server:"
echo "   source venv/bin/activate"
echo "   python manage.py runserver"
echo ""
echo "→ Platform URL:   http://localhost:8000"
echo "→ Admin Panel:    http://localhost:8000/admin-panel/"
echo "→ Django Admin:   http://localhost:8000/platform-admin/"
echo ""
