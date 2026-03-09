# investments/admin.py
from django.contrib import admin
from apps.investments.models import InvestmentCategory, InvestmentPlan, Investment, ROIPayment
from apps.deposits.models import PlatformBankAccount, BankDeposit, CryptoCurrency, CryptoDeposit
from apps.withdrawals.models import Withdrawal


@admin.register(InvestmentCategory)
class InvestmentCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'display_order']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(InvestmentPlan)
class InvestmentPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'roi_percentage', 'duration_value', 'duration_unit',
                    'minimum_amount', 'is_active', 'is_featured']
    list_filter = ['category', 'is_active', 'is_featured', 'duration_unit']
    search_fields = ['name']


@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    list_display = ['reference', 'user', 'plan', 'amount_invested', 'status', 'start_date', 'maturity_date']
    list_filter = ['status', 'plan__category']
    search_fields = ['reference', 'user__email']
    readonly_fields = ['reference', 'created_at']


@admin.register(PlatformBankAccount)
class PlatformBankAccountAdmin(admin.ModelAdmin):
    list_display = ['bank_name', 'account_holder', 'account_number', 'is_active']
    list_filter = ['bank_name', 'is_active']


@admin.register(BankDeposit)
class BankDepositAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'payment_reference', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['user__email', 'payment_reference']
    actions = ['approve_deposits']

    def approve_deposits(self, request, queryset):
        for deposit in queryset.filter(status='SUBMITTED'):
            deposit.approve(request.user)
    approve_deposits.short_description = "Approve selected bank deposits"


@admin.register(CryptoCurrency)
class CryptoCurrencyAdmin(admin.ModelAdmin):
    list_display = ['name', 'symbol', 'network', 'is_active']


@admin.register(CryptoDeposit)
class CryptoDepositAdmin(admin.ModelAdmin):
    list_display = ['user', 'cryptocurrency', 'crypto_amount', 'zar_amount', 'status', 'created_at']
    list_filter = ['status', 'cryptocurrency']
    search_fields = ['user__email', 'transaction_hash']
    actions = ['approve_crypto_deposits']

    def approve_crypto_deposits(self, request, queryset):
        for deposit in queryset.exclude(status='APPROVED'):
            deposit.approve(request.user)

    approve_crypto_deposits.short_description = "Approve selected crypto deposits"


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ['reference', 'user', 'amount', 'method', 'status', 'created_at']
    list_filter = ['status', 'method']
    search_fields = ['reference', 'user__email']
