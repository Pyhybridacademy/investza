"""
withdrawals/models.py
Withdrawal requests - bank and crypto
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class Withdrawal(models.Model):
    """A withdrawal request from a user."""

    METHOD_CHOICES = [
        ('BANK', 'Bank Transfer (ZAR)'),
        ('CRYPTO', 'Cryptocurrency'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('PROCESSING', 'Processing'),
        ('APPROVED', 'Approved'),
        ('COMPLETED', 'Completed'),
        ('REJECTED', 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='withdrawals'
    )
    reference = models.CharField(max_length=20, unique=True, blank=True)

    # Amount
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    fee = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    net_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    # Method
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)

    # Bank withdrawal fields
    bank_account = models.ForeignKey(
        'accounts.BankAccount',
        null=True, blank=True,
        on_delete=models.SET_NULL
    )

    # Crypto withdrawal fields
    crypto_currency = models.ForeignKey(
        'deposits.CryptoCurrency',
        null=True, blank=True,
        on_delete=models.SET_NULL
    )
    crypto_wallet_address = models.CharField(max_length=255, blank=True)
    crypto_amount = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)

    # ── Authorisation codes ─────────────────────────────────────
    withdrawal_code        = models.CharField(max_length=20, blank=True, help_text="Admin-issued one-time withdrawal authorisation code")
    withdrawal_code_used   = models.BooleanField(default=False)

    tax_code               = models.CharField(max_length=30, blank=True, help_text="SARS-issued tax clearance / withholding tax code")
    tax_certificate_issued = models.BooleanField(default=False)
    tax_pdf                = models.FileField(upload_to='tax_certificates/', blank=True, null=True)

    # Status
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    user_notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)

    # Processing
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='processed_withdrawals'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    transaction_proof = models.FileField(upload_to='withdrawal_proofs/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Withdrawal'
        ordering = ['-created_at']

    def __str__(self):
        return f"Withdrawal {self.reference} - R{self.amount} [{self.status}]"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"WDR-{uuid.uuid4().hex[:8].upper()}"
        if not self.net_amount:
            self.net_amount = self.amount - self.fee
        super().save(*args, **kwargs)

    def approve(self, admin_user):
        """Approve the withdrawal request."""
        self.status = 'APPROVED'
        self.processed_by = admin_user
        self.processed_at = timezone.now()
        self.save()

    def complete(self, admin_user, proof=None):
        """Mark withdrawal as completed and finalize wallet."""
        self.status = 'COMPLETED'
        self.processed_by = admin_user
        self.processed_at = timezone.now()
        if proof:
            self.transaction_proof = proof
        self.save()
        # Remove from pending
        wallet = self.user.get_wallet()
        wallet.pending_withdrawal -= self.amount
        if wallet.pending_withdrawal < 0:
            wallet.pending_withdrawal = 0
        wallet.save(update_fields=['pending_withdrawal'])

    def reject(self, admin_user, reason=''):
        """Reject withdrawal and refund to available balance."""
        self.status = 'REJECTED'
        self.admin_notes = reason
        self.processed_by = admin_user
        self.processed_at = timezone.now()
        self.save()
        # Refund to available balance
        wallet = self.user.get_wallet()
        wallet.available_balance += self.amount
        wallet.pending_withdrawal -= self.amount
        if wallet.pending_withdrawal < 0:
            wallet.pending_withdrawal = 0
        wallet.save(update_fields=['available_balance', 'pending_withdrawal'])
        from apps.accounts.models import WalletTransaction
        WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='REFUND',
            amount=self.amount,
            description=f"Withdrawal {self.reference} rejected - {reason}",
            balance_after=wallet.available_balance
        )


class WithdrawalCode(models.Model):
    """Admin-issued one-time withdrawal authorisation codes."""

    STATUS_CHOICES = [
        ('ACTIVE',  'Active — not yet used'),
        ('USED',    'Used'),
        ('EXPIRED', 'Expired'),
        ('REVOKED', 'Revoked'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code        = models.CharField(max_length=20, unique=True)
    issued_to   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='withdrawal_codes',
        help_text="User this code is issued to"
    )
    issued_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='issued_withdrawal_codes',
        help_text="Admin who generated this code"
    )
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')
    max_amount  = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True,
                                      help_text="Optional: limit how much this code authorises")
    notes       = models.TextField(blank=True)
    expires_at  = models.DateTimeField(null=True, blank=True,
                                       help_text="Leave blank for no expiry")
    used_at     = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Withdrawal Code'
        verbose_name_plural = 'Withdrawal Codes'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} → {self.issued_to.email} [{self.status}]"

    def is_valid(self, amount=None):
        """Check if this code can be used right now."""
        if self.status != 'ACTIVE':
            return False, "This withdrawal code has already been used, expired, or revoked."
        if self.expires_at and timezone.now() > self.expires_at:
            self.status = 'EXPIRED'
            self.save(update_fields=['status'])
            return False, "This withdrawal code has expired. Please contact management for a new code."
        if amount and self.max_amount and amount > self.max_amount:
            return False, f"This code only authorises withdrawals up to R{self.max_amount:,.2f}."
        return True, "OK"

    def mark_used(self):
        self.status = 'USED'
        self.used_at = timezone.now()
        self.save(update_fields=['status', 'used_at'])

    @staticmethod
    def generate_code():
        import random, string
        return 'WC-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
