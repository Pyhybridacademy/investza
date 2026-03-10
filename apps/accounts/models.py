"""
accounts/models.py
Custom User model, UserProfile, and Wallet for InvestZA
"""
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid
import random
import string


def generate_account_number():
    """Generate a unique 10-digit account number."""
    return ''.join(random.choices(string.digits, k=10))


def generate_referral_code():
    """Generate a unique 8-character alphanumeric referral code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


class User(AbstractUser):
    """Extended User model with extra fields for InvestZA."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('email address'), unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    id_number = models.CharField(max_length=20, blank=True, help_text="SA ID Number or Passport")
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)

    # Status
    is_verified = models.BooleanField(default=False, help_text="KYC verified user")
    is_active_investor = models.BooleanField(default=False)

    # Referral
    referral_code = models.CharField(max_length=8, unique=True, default=generate_referral_code)
    referred_by = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='referrals'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

    @property
    def full_name(self):
        return self.get_full_name() or self.username

    def get_wallet(self):
        wallet, _ = Wallet.objects.get_or_create(user=self)
        return wallet


class Wallet(models.Model):
    """User's main ZAR wallet on the platform."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    account_number = models.CharField(max_length=10, unique=True, default=generate_account_number)

    # Balances
    available_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    invested_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_earned = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    pending_withdrawal = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Wallet'

    def __str__(self):
        return f"Wallet #{self.account_number} - {self.user.full_name}"

    @property
    def total_balance(self):
        return self.available_balance + self.invested_balance

    def credit(self, amount, description="Credit"):
        """Add funds to available balance."""
        from decimal import Decimal
        amount = Decimal(str(amount))
        # Re-fetch from DB to get latest balance and avoid stale reads
        Wallet.objects.filter(pk=self.pk).update(
            available_balance=models.F('available_balance') + amount
        )
        self.refresh_from_db()
        WalletTransaction.objects.create(
            wallet=self,
            transaction_type='CREDIT',
            amount=amount,
            description=description,
            balance_after=self.available_balance
        )

    def debit(self, amount, description="Debit"):
        """Deduct funds from available balance."""
        from decimal import Decimal
        amount = Decimal(str(amount))
        # Re-fetch to get accurate balance
        self.refresh_from_db()
        if self.available_balance < amount:
            raise ValueError("Insufficient balance")
        Wallet.objects.filter(pk=self.pk).update(
            available_balance=models.F('available_balance') - amount
        )
        self.refresh_from_db()
        WalletTransaction.objects.create(
            wallet=self,
            transaction_type='DEBIT',
            amount=amount,
            description=description,
            balance_after=self.available_balance
        )


class WalletTransaction(models.Model):
    """Ledger entry for every wallet movement."""

    TRANSACTION_TYPES = [
        ('CREDIT', 'Credit'),
        ('DEBIT', 'Debit'),
        ('INVESTMENT', 'Investment'),
        ('ROI', 'ROI Return'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('DEPOSIT', 'Deposit'),
        ('REFUND', 'Refund'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.CharField(max_length=255)
    reference = models.CharField(max_length=100, blank=True)
    balance_after = models.DecimalField(max_digits=15, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Wallet Transaction'

    def __str__(self):
        return f"{self.transaction_type} - R{self.amount} ({self.wallet.user.full_name})"


class BankAccount(models.Model):
    """User's linked bank account for withdrawals."""

    BANK_CHOICES = [
        ('ABSA', 'ABSA Bank'),
        ('FNB', 'First National Bank (FNB)'),
        ('STANDARD', 'Standard Bank'),
        ('NEDBANK', 'Nedbank'),
        ('CAPITEC', 'Capitec Bank'),
        ('INVESTEC', 'Investec'),
        ('AFRICAN', 'African Bank'),
        ('DISCOVERY', 'Discovery Bank'),
        ('OTHER', 'Other'),
    ]

    ACCOUNT_TYPES = [
        ('CHEQUE', 'Cheque / Current'),
        ('SAVINGS', 'Savings'),
        ('TRANSMISSION', 'Transmission'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bank_accounts')
    bank_name = models.CharField(max_length=20, choices=BANK_CHOICES)
    account_holder = models.CharField(max_length=100)
    account_number = models.CharField(max_length=20)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='CHEQUE')
    branch_code = models.CharField(max_length=10, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Bank Account'

    def __str__(self):
        return f"{self.get_bank_name_display()} - {self.account_number}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            BankAccount.objects.filter(user=self.user, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)


class KYCDocument(models.Model):
    """KYC verification documents uploaded by users."""

    DOCUMENT_TYPES = [
        ('ID', 'South African ID'),
        ('PASSPORT', 'Passport'),
        ('DRIVERS', "Driver's License"),
        ('PROOF_ADDRESS', 'Proof of Address'),
        ('SELFIE', 'Selfie with ID'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kyc_documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    document_file = models.FileField(upload_to='kyc_documents/')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    admin_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='kyc_reviews'
    )

    class Meta:
        verbose_name = 'KYC Document'

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.user.full_name}"

class PlatformSettings(models.Model):
    """
    Singleton model — DB-managed platform configuration.
    Replaces .env values so admin can update without redeployment.
    """

    # ── Identity ─────────────────────────────────────────────────
    platform_name       = models.CharField(max_length=100, default='InvestZA')
    tagline             = models.CharField(max_length=200, default='Invest with Confidence', blank=True)
    support_email       = models.EmailField(default='support@investza.co.za')
    support_phone       = models.CharField(max_length=30, default='+27 (0) 10 000 0000')
    support_whatsapp    = models.CharField(max_length=30, blank=True, help_text='WhatsApp number (international format)')
    website_url         = models.URLField(blank=True, default='https://investza.co.za')
    fsp_number          = models.CharField(max_length=30, blank=True, help_text='FSP licence number')
    registered_address  = models.TextField(blank=True)

    # ── Currency ─────────────────────────────────────────────────
    currency_code       = models.CharField(max_length=5,  default='ZAR')
    currency_symbol     = models.CharField(max_length=5,  default='R')

    # ── Deposit limits ────────────────────────────────────────────
    min_deposit         = models.DecimalField(max_digits=12, decimal_places=2, default=500.00)
    max_deposit         = models.DecimalField(max_digits=12, decimal_places=2, default=5000000.00)

    # ── Withdrawal limits ─────────────────────────────────────────
    min_withdrawal      = models.DecimalField(max_digits=12, decimal_places=2, default=200.00)
    max_withdrawal      = models.DecimalField(max_digits=12, decimal_places=2, default=1000000.00)
    withdrawal_fee_pct  = models.DecimalField(max_digits=5, decimal_places=2, default=0.00,
                            help_text='Withdrawal fee as a percentage (e.g. 1.5 = 1.5%)')

    # ── Maintenance ───────────────────────────────────────────────
    maintenance_mode    = models.BooleanField(default=False,
                            help_text='Put platform in maintenance mode — blocks all user logins')
    maintenance_message = models.TextField(blank=True,
                            default='We are performing scheduled maintenance. We will be back shortly.')

    # ── Social / Legal ────────────────────────────────────────────
    twitter_url         = models.URLField(blank=True)
    linkedin_url        = models.URLField(blank=True)
    facebook_url        = models.URLField(blank=True)
    instagram_url       = models.URLField(blank=True)

    # ── Meta ──────────────────────────────────────────────────────
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        'accounts.User', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        verbose_name = 'Platform Settings'
        verbose_name_plural = 'Platform Settings'

    def __str__(self):
        return f'{self.platform_name} Settings'

    def save(self, *args, **kwargs):
        # Enforce singleton — only one row ever
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        """Return the singleton settings object, creating defaults if needed."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
