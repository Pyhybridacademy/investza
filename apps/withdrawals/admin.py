"""
withdrawals/admin.py
Django admin configuration for Withdrawal and WithdrawalCode models.
"""
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.db.models import Sum, Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import redirect, get_object_or_404

from .models import Withdrawal, WithdrawalCode


# ─────────────────────────────────────────────────────────────────
# CUSTOM FILTERS
# ─────────────────────────────────────────────────────────────────

class HasTaxCertFilter(SimpleListFilter):
    title = 'Tax Certificate'
    parameter_name = 'has_tax_cert'

    def lookups(self, request, model_admin):
        return [('yes', '✓ Has PDF'), ('no', '✗ No PDF')]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(tax_pdf='').exclude(tax_pdf__isnull=True)
        if self.value() == 'no':
            return queryset.filter(Q(tax_pdf='') | Q(tax_pdf__isnull=True))
        return queryset


class WithdrawalCodeStatusFilter(SimpleListFilter):
    title = 'Code Status'
    parameter_name = 'code_status'

    def lookups(self, request, model_admin):
        return WithdrawalCode.STATUS_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class HasMaxAmountFilter(SimpleListFilter):
    title = 'Amount Limit'
    parameter_name = 'has_limit'

    def lookups(self, request, model_admin):
        return [('yes', 'Has limit'), ('no', 'No limit')]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(max_amount__isnull=False)
        if self.value() == 'no':
            return queryset.filter(max_amount__isnull=True)
        return queryset


# ─────────────────────────────────────────────────────────────────
# WITHDRAWAL ADMIN
# ─────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────
# WITHDRAWAL CODE ADMIN
# ─────────────────────────────────────────────────────────────────

@admin.register(WithdrawalCode)
class WithdrawalCodeAdmin(admin.ModelAdmin):

    list_display = (
        'code_display', 'issued_to_link', 'issued_by_name', 'max_amount_fmt',
        'status_badge', 'expires_at_fmt', 'used_at_fmt', 'created_at_fmt', 'revoke_btn',
    )
    list_filter  = (WithdrawalCodeStatusFilter, HasMaxAmountFilter, 'created_at')
    search_fields = (
        'code', 'issued_to__email', 'issued_to__first_name',
        'issued_to__last_name', 'notes',
    )
    readonly_fields = ('id', 'code', 'issued_by', 'status', 'used_at', 'created_at')
    fieldsets = (
        ('🔑 Code Details', {
            'fields': ('id', 'code', 'status', 'used_at', 'created_at'),
        }),
        ('👤 Assignment', {
            'fields': ('issued_to', 'issued_by'),
        }),
        ('⚙️ Restrictions', {
            'fields': ('max_amount', 'expires_at'),
            'description': 'Optional limits. Leave blank for unrestricted.',
        }),
        ('📝 Notes', {
            'fields': ('notes',),
        }),
    )
    ordering = ('-created_at',)
    list_per_page = 30
    list_select_related = ('issued_to', 'issued_by')
    date_hierarchy = 'created_at'
    actions = ['action_revoke', 'action_regenerate_for_users']

    # ── Display columns ───────────────────────────────────────────

    def code_display(self, obj):
        colour = {
            'ACTIVE': '#198754', 'USED': '#0a1f44',
            'EXPIRED': '#856404', 'REVOKED': '#dc3545',
        }.get(obj.status, '#333')
        return format_html(
            '<span style="font-family:monospace;font-weight:700;font-size:13px;'
            'letter-spacing:1px;color:{};">{}</span>',
            colour, obj.code
        )
    code_display.short_description = 'Code'
    code_display.admin_order_field = 'code'

    def issued_to_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.issued_to.pk])
        return format_html(
            '<a href="{}" style="color:#0a1f44;font-weight:600;">{}</a>'
            '<br><span style="color:#6c757d;font-size:11px;">{}</span>',
            url, obj.issued_to.get_full_name(), obj.issued_to.email
        )
    issued_to_link.short_description = 'Issued To'
    issued_to_link.admin_order_field = 'issued_to__email'

    def issued_by_name(self, obj):
        if obj.issued_by:
            return format_html(
                '<span style="font-size:12px;">{}</span>',
                obj.issued_by.get_full_name() or obj.issued_by.email
            )
        return format_html('<span style="color:#adb5bd;font-size:11px;">System</span>')
    issued_by_name.short_description = 'Issued By'

    def max_amount_fmt(self, obj):
        if obj.max_amount:
            amount = f"{obj.max_amount:,.2f}"
            return format_html(
                '<span style="font-family:monospace;font-size:12px;font-weight:600;">R {}</span>',
                amount
            )
        return format_html('<span style="color:#adb5bd;font-size:11px;">No limit</span>')

    _CODE_STATUS_STYLES = {
        'ACTIVE':  ('#0f5132', '#d1e7dd', '●'),
        'USED':    ('#084298', '#cfe2ff', '✓'),
        'EXPIRED': ('#856404', '#fff3cd', '⏰'),
        'REVOKED': ('#842029', '#f8d7da', '✕'),
    }

    def status_badge(self, obj):
        colour, bg, icon = self._CODE_STATUS_STYLES.get(obj.status, ('#333', '#eee', '?'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:99px;'
            'font-size:11px;font-weight:700;">{} {}</span>',
            bg, colour, icon, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def expires_at_fmt(self, obj):
        if not obj.expires_at:
            return format_html('<span style="color:#adb5bd;font-size:11px;">Never</span>')
        colour = '#dc3545' if obj.expires_at < timezone.now() else '#495057'
        return format_html(
            '<span style="font-size:12px;color:{};">{}</span>',
            colour, obj.expires_at.strftime('%d %b %Y %H:%M')
        )
    expires_at_fmt.short_description = 'Expires'
    expires_at_fmt.admin_order_field = 'expires_at'

    def used_at_fmt(self, obj):
        if not obj.used_at:
            return format_html('<span style="color:#adb5bd;font-size:11px;">—</span>')
        return format_html(
            '<span style="font-size:12px;color:#198754;">{}</span>',
            obj.used_at.strftime('%d %b %Y %H:%M')
        )
    used_at_fmt.short_description = 'Used At'
    used_at_fmt.admin_order_field = 'used_at'

    def created_at_fmt(self, obj):
        return format_html(
            '<span style="font-size:12px;color:#495057;">{}</span>',
            obj.created_at.strftime('%d %b %Y %H:%M')
        )
    created_at_fmt.short_description = 'Created'
    created_at_fmt.admin_order_field = 'created_at'

    def revoke_btn(self, obj):
        if obj.status == 'ACTIVE':
            url = reverse('admin:withdrawalcode_revoke', args=[obj.pk])
            return format_html(
                '<a href="{}" style="background:#dc3545;color:#fff;padding:3px 10px;'
                'border-radius:5px;font-size:11px;text-decoration:none;">Revoke</a>', url
            )
        return format_html('<span style="color:#adb5bd;font-size:11px;">—</span>')
    revoke_btn.short_description = 'Action'

    # ── Bulk actions ──────────────────────────────────────────────

    @admin.action(description='✕ Revoke selected codes')
    def action_revoke(self, request, queryset):
        n = queryset.filter(status='ACTIVE').update(status='REVOKED')
        self.message_user(request, f'{n} code(s) revoked.', messages.WARNING)

    @admin.action(description='🔑 Generate a fresh code for each selected code\'s user')
    def action_regenerate_for_users(self, request, queryset):
        seen, created = set(), 0
        for code in queryset:
            uid = code.issued_to_id
            if uid not in seen:
                seen.add(uid)
                WithdrawalCode.objects.create(
                    code=WithdrawalCode.generate_code(),
                    issued_to=code.issued_to,
                    issued_by=request.user,
                )
                created += 1
        self.message_user(request,
            f'{created} new code(s) generated. They appear at the top of the list.',
            messages.SUCCESS)

    # ── Custom URL routes ─────────────────────────────────────────

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('generate/',
                 self.admin_site.admin_view(self.generate_code_view),
                 name='withdrawalcode_generate'),
            path('<uuid:pk>/revoke/',
                 self.admin_site.admin_view(self.revoke_code_view),
                 name='withdrawalcode_revoke'),
        ]
        return custom + urls

    def generate_code_view(self, request):
        if request.method != 'POST':
            return redirect(reverse('admin:withdrawals_withdrawalcode_changelist'))

        from django.contrib.auth import get_user_model
        from decimal import Decimal, InvalidOperation
        from django.utils.dateparse import parse_datetime

        User = get_user_model()
        try:
            target = User.objects.get(pk=request.POST.get('user_id', '').strip())
        except (User.DoesNotExist, ValueError):
            self.message_user(request, 'User not found.', messages.ERROR)
            return redirect(reverse('admin:withdrawals_withdrawalcode_changelist'))

        max_amount = None
        if request.POST.get('max_amount', '').strip():
            try:
                max_amount = Decimal(request.POST['max_amount'].strip())
            except InvalidOperation:
                self.message_user(request, 'Invalid max amount.', messages.ERROR)
                return redirect(reverse('admin:withdrawals_withdrawalcode_changelist'))

        expires_at = None
        if request.POST.get('expires_at', '').strip():
            expires_at = parse_datetime(request.POST['expires_at'].strip())

        code = WithdrawalCode.objects.create(
            code=WithdrawalCode.generate_code(),
            issued_to=target,
            issued_by=request.user,
            max_amount=max_amount,
            expires_at=expires_at,
            notes=request.POST.get('notes', '').strip(),
        )
        self.message_user(request,
            f'Code {code.code} generated for {target.get_full_name()} ({target.email}). '
            'Copy it now and share via live chat or email — it will not be displayed again.',
            messages.SUCCESS)
        return redirect(reverse('admin:withdrawals_withdrawalcode_changelist'))

    def revoke_code_view(self, request, pk):
        code = get_object_or_404(WithdrawalCode, pk=pk)
        if code.status == 'ACTIVE':
            code.status = 'REVOKED'
            code.save(update_fields=['status'])
            self.message_user(request,
                f'Code {code.code} revoked for {code.issued_to.email}.', messages.WARNING)
        else:
            self.message_user(request,
                f'Code is already {code.get_status_display()} — nothing changed.', messages.WARNING)
        return redirect(reverse('admin:withdrawals_withdrawalcode_changelist'))

    # ── Auto-set issued_by on save ────────────────────────────────

    def save_model(self, request, obj, form, change):
        if not change:
            if not obj.code:
                obj.code = WithdrawalCode.generate_code()
            obj.issued_by = request.user
        super().save_model(request, obj, form, change)

    # ── Changelist stats ──────────────────────────────────────────

    def changelist_view(self, request, extra_context=None):
        qs = self.get_queryset(request)
        extra_context = extra_context or {}
        extra_context['code_stats'] = {
            'active':  qs.filter(status='ACTIVE').count(),
            'used':    qs.filter(status='USED').count(),
            'expired': qs.filter(status='EXPIRED').count(),
            'revoked': qs.filter(status='REVOKED').count(),
            'total':   qs.count(),
        }
        return super().changelist_view(request, extra_context=extra_context)