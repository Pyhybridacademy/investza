"""
deposits/models.py
Bank Deposit and Crypto Deposit models
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class PlatformBankAccount(models.Model):
    """Bank accounts owned by the platform, shown to users for deposits."""

    BANK_CHOICES = [
        ('ABSA', 'ABSA Bank'),
        ('FNB', 'First National Bank (FNB)'),
        ('STANDARD', 'Standard Bank'),
        ('NEDBANK', 'Nedbank'),
        ('CAPITEC', 'Capitec Bank'),
        ('INVESTEC', 'Investec'),
    ]

    bank_name = models.CharField(max_length=20, choices=BANK_CHOICES)
    account_holder = models.CharField(max_length=100)
    account_number = models.CharField(max_length=30)
    account_type = models.CharField(max_length=30, default='Cheque')
    branch_code = models.CharField(max_length=10)
    branch_name = models.CharField(max_length=100, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)
    reference_prefix = models.CharField(
        max_length=10, default='INZ',
        help_text="Prefix for payment reference (e.g. INZ-<account_number>)"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Platform Bank Account'

    def __str__(self):
        return f"{self.get_bank_name_display()} - {self.account_number}"


class BankDeposit(models.Model):
    """A deposit request made via bank transfer."""

    STATUS_CHOICES = [
        ('PENDING', 'Pending - Awaiting Payment'),
        ('SUBMITTED', 'Submitted - Proof Uploaded'),
        ('VERIFYING', 'Verifying'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bank_deposits'
    )
    platform_account = models.ForeignKey(
        PlatformBankAccount,
        on_delete=models.SET_NULL,
        null=True
    )

    amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_reference = models.CharField(max_length=50, unique=True)
    proof_of_payment = models.FileField(upload_to='deposit_proofs/', blank=True, null=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    admin_notes = models.TextField(blank=True)

    # Admin processing
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_deposits'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Bank Deposit'
        ordering = ['-created_at']

    def __str__(self):
        return f"Deposit R{self.amount} by {self.user.full_name} [{self.status}]"

    def save(self, *args, **kwargs):
        if not self.payment_reference:
            prefix = self.platform_account.reference_prefix if self.platform_account else 'INZ'
            from apps.accounts.models import Wallet
            wallet = self.user.get_wallet()

            unique_code = str(uuid.uuid4())[:8].upper()
            self.payment_reference = f"{prefix}-{wallet.account_number}-{unique_code}"

        super().save(*args, **kwargs)

    def approve(self, admin_user):
        """Approve deposit and credit user wallet."""
        if self.status == 'APPROVED':
            return  # Prevent double crediting
        self.status = 'APPROVED'
        self.approved_by = admin_user
        self.approved_at = timezone.now()
        self.save()
        # Credit user wallet
        wallet = self.user.get_wallet()
        wallet.credit(self.amount, f"Bank deposit approved - Ref: {self.payment_reference}")


class CryptoCurrency(models.Model):
    """Supported cryptocurrencies on the platform."""

    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=10, unique=True)
    wallet_address = models.CharField(max_length=255)
    network = models.CharField(max_length=50, blank=True, help_text="e.g. ERC-20, TRC-20")
    logo = models.ImageField(upload_to='crypto_logos/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    minimum_deposit = models.DecimalField(max_digits=15, decimal_places=8, default=0.001)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Cryptocurrency'
        verbose_name_plural = 'Cryptocurrencies'
        ordering = ['display_order', 'name']

    def __str__(self):
        return f"{self.name} ({self.symbol})"


class CryptoDeposit(models.Model):
    """A deposit request made via cryptocurrency."""

    STATUS_CHOICES = [
        ('PENDING', 'Pending - Awaiting Transfer'),
        ('SUBMITTED', 'Submitted - Hash Provided'),
        ('VERIFYING', 'Verifying on Blockchain'),
        ('APPROVED', 'Approved & Credited'),
        ('REJECTED', 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='crypto_deposits'
    )
    cryptocurrency = models.ForeignKey(CryptoCurrency, on_delete=models.PROTECT)

    # Amounts
    crypto_amount = models.DecimalField(max_digits=20, decimal_places=8)
    zar_amount = models.DecimalField(max_digits=15, decimal_places=2)
    exchange_rate_used = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Blockchain
    transaction_hash = models.CharField(max_length=255, blank=True)
    from_wallet_address = models.CharField(max_length=255, blank=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    admin_notes = models.TextField(blank=True)

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_crypto_deposits'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Crypto Deposit'
        ordering = ['-created_at']

    def __str__(self):
        return f"Crypto Deposit {self.crypto_amount} {self.cryptocurrency.symbol} by {self.user.full_name}"

    def approve(self, admin_user):
        """Approve crypto deposit and credit user wallet in ZAR."""
        if self.status == 'APPROVED':
            return  # Prevent double crediting
        self.status = 'APPROVED'
        self.approved_by = admin_user
        self.approved_at = timezone.now()
        self.save()
        wallet = self.user.get_wallet()
        hash_preview = self.transaction_hash[:20] if self.transaction_hash else 'N/A'
        wallet.credit(
            self.zar_amount,
            f"Crypto deposit: {self.crypto_amount} {self.cryptocurrency.symbol} - Hash: {hash_preview}..."
        )