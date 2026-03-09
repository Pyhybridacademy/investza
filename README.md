# InvestZA - Multi-Asset Investment Platform

A secure, full-featured investment platform for the South African market built with **Django** + **Tailwind CSS**.

---

## 🏦 Platform Overview

InvestZA allows users to invest in three asset classes:
- **Gold** – gold-backed investment plans
- **Real Estate** – SA property portfolio plans
- **Cryptocurrency** – managed crypto trading plans

All transactions are in **South African Rand (ZAR / R)**.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Redis (for task queue)
- PostgreSQL (recommended for production) or SQLite (development)

### 1. Clone & Setup
```bash
git clone <repo-url>
cd investza
chmod +x setup.sh
./setup.sh
```

### 2. Configure Environment
```bash
cp .env.example .env
nano .env   # Fill in your values
```

### 3. Run Development Server
```bash
source venv/bin/activate
python manage.py runserver
```

Visit: http://localhost:8000

---

## 📁 Project Structure

```
investza/
├── investza/               # Core Django project
│   ├── settings.py         # All settings (uses python-decouple)
│   ├── urls.py             # Root URL routing
│   ├── celery.py           # Celery task queue config
│   └── wsgi.py
│
├── apps/
│   ├── accounts/           # Users, wallets, KYC, authentication
│   │   ├── models.py       # User, Wallet, WalletTransaction, BankAccount, KYCDocument
│   │   ├── views.py        # Auth, dashboard, profile views
│   │   ├── forms.py        # Registration, login, profile forms
│   │   ├── middleware.py   # LastSeen tracker
│   │   ├── context_processors.py
│   │   └── urls/           # Modular URL files (public, auth, dashboard)
│   │
│   ├── investments/        # Investment categories, plans, active investments
│   │   ├── models.py       # InvestmentCategory, InvestmentPlan, Investment, ROIPayment
│   │   ├── views.py        # Investment listing, creation, management
│   │   └── forms.py
│   │
│   ├── deposits/           # Bank and crypto deposit system
│   │   ├── models.py       # PlatformBankAccount, BankDeposit, CryptoCurrency, CryptoDeposit
│   │   ├── views.py        # Deposit creation and verification flow
│   │   └── forms.py
│   │
│   ├── withdrawals/        # Withdrawal request system
│   │   ├── models.py       # Withdrawal (bank + crypto)
│   │   └── views.py        # Withdrawal creation and tracking
│   │
│   └── administration/     # Custom admin panel
│       ├── views.py        # Full admin management views
│       └── urls.py
│
├── templates/              # All HTML templates (to be added)
├── static/                 # CSS, JS, images
├── fixtures/
│   └── initial_data.json   # Seed data: plans, categories, crypto
├── requirements.txt
├── .env.example
├── manage.py
└── setup.sh
```

---

## 💡 Key Features

### User Features
| Feature | Description |
|---|---|
| Registration | Email-based registration with referral code support |
| KYC Verification | Upload ID, passport, proof of address |
| Wallet | ZAR wallet with available + invested balance tracking |
| Investments | Select plan → enter amount → auto-calculate ROI → activate |
| Bank Deposit | Generate payment details → transfer → upload proof → admin verifies |
| Crypto Deposit | Select crypto → get wallet address → submit TX hash → admin verifies |
| Withdrawal | Request bank or crypto withdrawal → admin approval → processed |
| Transaction History | Full ledger of all wallet movements |

### Admin Features
| Feature | Description |
|---|---|
| User Management | View, verify (KYC), activate/deactivate, credit/debit users |
| Deposit Approval | Approve/reject bank and crypto deposits |
| Withdrawal Processing | Approve, complete, or reject withdrawal requests |
| Investment Monitoring | View all active investments and performance |
| Plan Management | Create/edit investment plans and ROI settings |
| Platform Accounts | Manage company bank accounts for deposits |
| Financial Reports | Summary statistics and performance data |

---

## 🗄️ Database Models

### accounts app
- **User** – Extended AbstractUser with phone, DOB, ID, KYC status, referral
- **Wallet** – ZAR wallet per user with available/invested/earned balances
- **WalletTransaction** – Immutable ledger entries for all wallet changes
- **BankAccount** – User's personal bank accounts for withdrawals
- **KYCDocument** – Identity documents for verification

### investments app
- **InvestmentCategory** – Gold, Real Estate, Crypto
- **InvestmentPlan** – Specific plans with ROI%, duration, min/max amounts
- **Investment** – Active investment record linking user ↔ plan
- **ROIPayment** – Records each ROI payout

### deposits app
- **PlatformBankAccount** – Company bank accounts assigned to deposit requests
- **BankDeposit** – Bank transfer deposit request with proof upload
- **CryptoCurrency** – Supported cryptos (BTC, ETH, USDT)
- **CryptoDeposit** – Crypto deposit request with TX hash verification

### withdrawals app
- **Withdrawal** – Bank or crypto withdrawal request with approval workflow

---

## ⚙️ Configuration (.env)

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key (generate a new one!) |
| `DEBUG` | `True` for dev, `False` for production |
| `DATABASE_URL` | SQLite (dev) or PostgreSQL (prod) URL |
| `REDIS_URL` | Redis URL for Celery task queue |
| `EMAIL_*` | SMTP configuration for emails |
| `MIN_DEPOSIT` | Minimum deposit amount in ZAR |
| `MIN_WITHDRAWAL` | Minimum withdrawal amount in ZAR |

---

## 🔒 Security Notes

- All URLs use CSRF protection
- Password hashing via Django's PBKDF2
- Session-based authentication
- Admin panel requires `is_staff` or `is_superuser`
- In production: enable all `SECURE_*` settings in `settings.py`
- KYC verification before large transactions (recommended)

---

## 📦 Tech Stack

| Component | Technology |
|---|---|
| Backend | Django 4.2 |
| API | Django REST Framework |
| Frontend | Tailwind CSS |
| Forms | django-crispy-forms + crispy-tailwind |
| Task Queue | Celery + Redis |
| Static Files | WhiteNoise |
| Database | SQLite (dev) / PostgreSQL (prod) |

---

## 🛠️ Development Commands

```bash
# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Load seed data
python manage.py loaddata fixtures/initial_data.json

# Collect static files
python manage.py collectstatic

# Start Celery worker
celery -A investza worker -l info

# Start development server
python manage.py runserver
```

---

## 📧 Support

**Platform:** InvestZA  
**Email:** support@investza.co.za  
**Phone:** +27 (0) 10 000 0000  

---

*Built for the South African investment market. All amounts in ZAR.*
