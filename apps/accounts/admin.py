"""
Register all models with Django admin for basic access.
The custom admin panel handles the rich UI.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Wallet, WalletTransaction, BankAccount, KYCDocument


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'full_name', 'is_verified', 'is_active', 'date_joined']
    list_filter = ['is_verified', 'is_active', 'is_staff']
    search_fields = ['email', 'first_name', 'last_name']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('InvestZA Profile', {
            'fields': ('phone_number', 'date_of_birth', 'id_number', 'is_verified',
                       'referral_code', 'referred_by', 'last_seen')
        }),
    )


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'account_number', 'available_balance', 'invested_balance', 'total_earned']
    search_fields = ['user__email', 'account_number']
    readonly_fields = ['account_number', 'created_at', 'updated_at']


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'transaction_type', 'amount', 'description', 'created_at']
    list_filter = ['transaction_type']
    search_fields = ['wallet__user__email', 'description', 'reference']
    readonly_fields = ['created_at']


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ['user', 'bank_name', 'account_number', 'account_type', 'is_primary']
    list_filter = ['bank_name', 'is_primary']


@admin.register(KYCDocument)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display = ['user', 'document_type', 'status', 'submitted_at']
    list_filter = ['status', 'document_type']
    actions = ['approve_documents']

    def approve_documents(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='APPROVED', reviewed_at=timezone.now(), reviewed_by=request.user)
        # Mark users as verified
        for doc in queryset:
            doc.user.is_verified = True
            doc.user.save(update_fields=['is_verified'])
    approve_documents.short_description = "Approve selected KYC documents"

# PlatformSettings
try:
    from apps.accounts.models import PlatformSettings
    @admin.register(PlatformSettings)
    class PlatformSettingsAdmin(admin.ModelAdmin):
        list_display = ['platform_name', 'support_email', 'currency_code', 'maintenance_mode', 'updated_at']
        fieldsets = (
            ('Identity',  {'fields': ('platform_name', 'tagline', 'website_url', 'fsp_number', 'registered_address')}),
            ('Contact',   {'fields': ('support_email', 'support_phone', 'support_whatsapp')}),
            ('Currency',  {'fields': ('currency_code', 'currency_symbol')}),
            ('Limits',    {'fields': ('min_deposit', 'max_deposit', 'min_withdrawal', 'max_withdrawal', 'withdrawal_fee_pct')}),
            ('Social',    {'fields': ('twitter_url', 'linkedin_url', 'facebook_url', 'instagram_url')}),
            ('System',    {'fields': ('maintenance_mode', 'maintenance_message', 'updated_by')}),
        )
        def has_add_permission(self, request): return not PlatformSettings.objects.exists()
        def has_delete_permission(self, request, obj=None): return False
except Exception:
    pass
