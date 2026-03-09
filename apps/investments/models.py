"""
investments/models.py
Investment Plans, Categories, and Active Investments
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
from decimal import Decimal


class InvestmentCategory(models.Model):
    """Top-level investment categories: Gold, Real Estate, Crypto."""

    CATEGORY_ICONS = [
        ('gold', 'Gold Bars Icon'),
        ('real_estate', 'Building Icon'),
        ('crypto', 'Crypto Coin Icon'),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    icon = models.CharField(max_length=20, choices=CATEGORY_ICONS, default='gold')
    image = models.ImageField(upload_to='investment_categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Investment Category'
        verbose_name_plural = 'Investment Categories'
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class InvestmentPlan(models.Model):
    """Specific investment plans within a category."""

    DURATION_UNITS = [
        ('DAYS', 'Days'),
        ('WEEKS', 'Weeks'),
        ('MONTHS', 'Months'),
    ]

    ROI_TYPES = [
        ('FIXED', 'Fixed Rate'),
        ('TIERED', 'Tiered Rate (based on amount)'),
        ('COMPOUND', 'Compound Interest'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(InvestmentCategory, on_delete=models.CASCADE, related_name='plans')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    # Capital limits (ZAR)
    minimum_amount = models.DecimalField(max_digits=12, decimal_places=2, default=500.00)
    maximum_amount = models.DecimalField(max_digits=12, decimal_places=2, default=1000000.00)

    # Duration
    duration_value = models.PositiveIntegerField(default=30)
    duration_unit = models.CharField(max_length=10, choices=DURATION_UNITS, default='DAYS')

    # Returns
    roi_type = models.CharField(max_length=10, choices=ROI_TYPES, default='FIXED')
    roi_percentage = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0.01), MaxValueValidator(500)],
        help_text="ROI percentage for the full duration period"
    )
    daily_roi = models.DecimalField(
        max_digits=5, decimal_places=4, default=0.0000,
        help_text="Auto-calculated daily ROI"
    )

    # Principal return
    returns_principal = models.BooleanField(default=True, help_text="Return capital at maturity")

    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Investment Plan'
        ordering = ['category', 'display_order', 'minimum_amount']

    def __str__(self):
        return f"{self.category.name} - {self.name} ({self.roi_percentage}%)"

    @property
    def duration_in_days(self):
        if self.duration_unit == 'DAYS':
            return self.duration_value
        elif self.duration_unit == 'WEEKS':
            return self.duration_value * 7
        elif self.duration_unit == 'MONTHS':
            return self.duration_value * 30
        return self.duration_value

    def calculate_roi(self, amount):
        """Calculate expected profit for a given amount."""
        return (Decimal(str(amount)) * self.roi_percentage) / Decimal('100')

    def calculate_total_return(self, amount):
        """Calculate total return including principal."""
        profit = self.calculate_roi(amount)
        if self.returns_principal:
            return Decimal(str(amount)) + profit
        return profit

    def save(self, *args, **kwargs):
        # Auto-calculate daily ROI
        if self.duration_in_days > 0:
            self.daily_roi = self.roi_percentage / Decimal(str(self.duration_in_days))
        super().save(*args, **kwargs)


class Investment(models.Model):
    """An active or completed investment made by a user."""

    STATUS_CHOICES = [
        ('PENDING', 'Pending Activation'),
        ('ACTIVE', 'Active'),
        ('MATURED', 'Matured'),
        ('CANCELLED', 'Cancelled'),
        ('WITHDRAWN', 'Withdrawn'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='investments'
    )
    plan = models.ForeignKey(InvestmentPlan, on_delete=models.PROTECT, related_name='investments')

    # Capital
    amount_invested = models.DecimalField(max_digits=15, decimal_places=2)
    expected_roi = models.DecimalField(max_digits=15, decimal_places=2)
    expected_total = models.DecimalField(max_digits=15, decimal_places=2)

    # Actual returns
    actual_roi_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    # Timeline
    start_date = models.DateTimeField(null=True, blank=True)
    maturity_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Status
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')

    # Reference
    reference = models.CharField(max_length=20, unique=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Investment'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reference} - {self.user.full_name} - R{self.amount_invested}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"INV-{uuid.uuid4().hex[:8].upper()}"
        if not self.expected_roi:
            self.expected_roi = self.plan.calculate_roi(self.amount_invested)
        if not self.expected_total:
            self.expected_total = self.plan.calculate_total_return(self.amount_invested)
        super().save(*args, **kwargs)

    def activate(self):
        """Activate investment and set maturity date."""
        self.status = 'ACTIVE'
        self.start_date = timezone.now()
        self.maturity_date = self.start_date + timezone.timedelta(days=self.plan.duration_in_days)
        self.save()

    @property
    def progress_percentage(self):
        """How far through the investment period we are."""
        if not self.start_date or not self.maturity_date:
            return 0
        total_duration = (self.maturity_date - self.start_date).total_seconds()
        elapsed = (timezone.now() - self.start_date).total_seconds()
        if total_duration <= 0:
            return 100
        return min(100, int((elapsed / total_duration) * 100))

    @property
    def days_remaining(self):
        if not self.maturity_date:
            return None
        delta = self.maturity_date - timezone.now()
        return max(0, delta.days)

    @property
    def is_matured(self):
        if not self.maturity_date:
            return False
        return timezone.now() >= self.maturity_date


class ROIPayment(models.Model):
    """Records each ROI payment made to a user for an investment."""

    investment = models.ForeignKey(Investment, on_delete=models.CASCADE, related_name='roi_payments')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = 'ROI Payment'
        ordering = ['-payment_date']

    def __str__(self):
        return f"ROI R{self.amount} for {self.investment.reference}"
