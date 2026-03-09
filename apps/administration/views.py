"""
administration/views.py
Admin panel - full management of users, investments, deposits, withdrawals
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from datetime import timedelta

User = get_user_model()


def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


# Single decorator used throughout this file
staff_required = user_passes_test(is_admin, login_url='/accounts/login/')


@login_required
@staff_required
def admin_dashboard(request):
    from apps.investments.models import Investment
    from apps.deposits.models import BankDeposit, CryptoDeposit
    from apps.withdrawals.models import Withdrawal
    from apps.accounts.models import Wallet

    total_users = User.objects.filter(is_staff=False).count()
    new_users_today = User.objects.filter(
        date_joined__date=timezone.now().date(), is_staff=False
    ).count()
    total_invested = Investment.objects.filter(
        status='ACTIVE'
    ).aggregate(total=Sum('amount_invested'))['total'] or 0
    total_wallet_balance = Wallet.objects.aggregate(
        total=Sum('available_balance')
    )['total'] or 0
    pending_bank_deposits    = BankDeposit.objects.filter(status__in=['SUBMITTED','VERIFYING']).count()
    pending_crypto_deposits  = CryptoDeposit.objects.filter(status__in=['SUBMITTED','VERIFYING']).count()
    pending_withdrawals      = Withdrawal.objects.filter(status='PENDING').count()
    recent_deposits          = BankDeposit.objects.filter(
        status__in=['SUBMITTED','VERIFYING']
    ).select_related('user').order_by('-created_at')[:10]
    recent_withdrawals       = Withdrawal.objects.filter(
        status='PENDING'
    ).select_related('user').order_by('-created_at')[:10]
    thirty_days_ago          = timezone.now() - timedelta(days=30)
    new_investments          = Investment.objects.filter(created_at__gte=thirty_days_ago).count()

    context = {
        'total_users': total_users,
        'new_users_today': new_users_today,
        'total_invested': total_invested,
        'total_wallet_balance': total_wallet_balance,
        'pending_bank_deposits': pending_bank_deposits,
        'pending_crypto_deposits': pending_crypto_deposits,
        'pending_withdrawals': pending_withdrawals,
        'recent_deposits': recent_deposits,
        'recent_withdrawals': recent_withdrawals,
        'new_investments': new_investments,
        'total_pending_actions': pending_bank_deposits + pending_crypto_deposits + pending_withdrawals,
    }
    return render(request, 'admin_panel/dashboard.html', context)


@login_required
@staff_required
def admin_users(request):
    search = request.GET.get('search', '')
    users  = User.objects.filter(is_staff=False).select_related('wallet')
    if search:
        users = users.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    users = users.order_by('-date_joined')
    return render(request, 'admin_panel/users.html', {'users': users, 'search': search})


@login_required
@staff_required
def admin_user_detail(request, pk):
    from apps.investments.models import Investment
    from apps.deposits.models import BankDeposit, CryptoDeposit
    from apps.withdrawals.models import Withdrawal

    user   = get_object_or_404(User, pk=pk)
    wallet = user.get_wallet()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'verify':
            user.is_verified = True
            user.save()
            messages.success(request, f"{user.get_full_name()} has been KYC verified.")
        elif action == 'deactivate':
            user.is_active = False
            user.save()
            messages.warning(request, f"{user.get_full_name()} account has been deactivated.")
        elif action == 'activate':
            user.is_active = True
            user.save()
            messages.success(request, f"{user.get_full_name()} account has been activated.")
        elif action == 'credit':
            from decimal import Decimal
            amount = Decimal(request.POST.get('amount', '0'))
            note   = request.POST.get('note', 'Admin credit')
            if amount > 0:
                wallet.credit(amount, note)
                messages.success(request, f"R{amount:,.2f} credited to {user.get_full_name()}")
        elif action == 'debit':
            from decimal import Decimal
            amount = Decimal(request.POST.get('amount', '0'))
            note   = request.POST.get('note', 'Admin debit')
            if amount > 0 and wallet.available_balance >= amount:
                wallet.debit(amount, note)
                messages.success(request, f"R{amount:,.2f} debited from {user.get_full_name()}")
        return redirect('admin_user_detail', pk=pk)

    context = {
        'profile_user': user,
        'wallet': wallet,
        'investments':    Investment.objects.filter(user=user).order_by('-created_at'),
        'bank_deposits':  BankDeposit.objects.filter(user=user).order_by('-created_at'),
        'crypto_deposits':CryptoDeposit.objects.filter(user=user).order_by('-created_at'),
        'withdrawals':    Withdrawal.objects.filter(user=user).order_by('-created_at'),
    }
    return render(request, 'admin_panel/user_detail.html', context)


@login_required
@staff_required
def admin_deposits(request):
    from apps.deposits.models import BankDeposit, CryptoDeposit
    status_filter  = request.GET.get('status', '')
    bank_deposits  = BankDeposit.objects.select_related('user','platform_account').order_by('-created_at')
    crypto_deposits= CryptoDeposit.objects.select_related('user','cryptocurrency').order_by('-created_at')
    if status_filter:
        bank_deposits   = bank_deposits.filter(status=status_filter)
        crypto_deposits = crypto_deposits.filter(status=status_filter)
    return render(request, 'admin_panel/deposits.html', {
        'bank_deposits':   bank_deposits[:50],
        'crypto_deposits': crypto_deposits[:50],
        'status_filter':   status_filter,
    })


@login_required
@staff_required
def admin_approve_bank_deposit(request, pk):
    from apps.deposits.models import BankDeposit
    deposit = get_object_or_404(BankDeposit, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            deposit.approve(request.user)
            messages.success(request,
                f"Deposit of R{deposit.amount:,.2f} approved and credited to {deposit.user.get_full_name()}")
        elif action == 'reject':
            reason = request.POST.get('reason', 'Rejected by admin')
            deposit.status     = 'REJECTED'
            deposit.admin_notes= reason
            deposit.save()
            messages.warning(request, "Deposit rejected.")
        return redirect('admin_deposits')
    return render(request, 'admin_panel/deposit_detail.html', {'deposit': deposit})


@login_required
@staff_required
def admin_approve_crypto_deposit(request, pk):
    from apps.deposits.models import CryptoDeposit
    deposit = get_object_or_404(CryptoDeposit, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('admin_notes', '').strip()
        if action == 'approve':
            if notes:
                deposit.admin_notes = notes
                deposit.save(update_fields=['admin_notes'])
            deposit.approve(request.user)
            messages.success(request, f"Crypto deposit approved. R{deposit.zar_amount:,.2f} credited to {deposit.user.get_full_name()}.")
        elif action == 'reject':
            deposit.status      = 'REJECTED'
            deposit.admin_notes = notes or 'Rejected by admin'
            deposit.save(update_fields=['status', 'admin_notes', 'updated_at'])
            messages.warning(request, "Crypto deposit rejected.")
        return redirect('admin_deposits')
    return render(request, 'admin_panel/crypto_deposit_detail.html', {'deposit': deposit})


@login_required
@staff_required
def admin_withdrawals(request):
    from apps.withdrawals.models import Withdrawal
    status_filter = request.GET.get('status', '')
    withdrawals   = Withdrawal.objects.select_related(
        'user','bank_account','crypto_currency'
    ).order_by('-created_at')
    if status_filter:
        withdrawals = withdrawals.filter(status=status_filter)
    return render(request, 'admin_panel/withdrawals.html', {
        'withdrawals':   withdrawals[:100],
        'status_filter': status_filter,
    })


@login_required
@staff_required
def admin_process_withdrawal(request, pk):
    from apps.withdrawals.models import Withdrawal
    withdrawal = get_object_or_404(Withdrawal, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            withdrawal.approve(request.user)
            messages.success(request, f"Withdrawal {withdrawal.reference} approved.")
        elif action == 'complete':
            withdrawal.complete(request.user)
            messages.success(request, f"Withdrawal {withdrawal.reference} marked as completed.")
        elif action == 'reject':
            reason = request.POST.get('reason', 'Rejected by admin')
            withdrawal.reject(request.user, reason)
            messages.warning(request, "Withdrawal rejected. Funds refunded to user.")
        return redirect('admin_withdrawals')
    return render(request, 'admin_panel/withdrawal_detail.html', {'withdrawal': withdrawal})


@login_required
@staff_required
def admin_investments(request):
    from apps.investments.models import Investment
    investments  = Investment.objects.select_related('user','plan__category').order_by('-created_at')
    total_active = investments.filter(status='ACTIVE').aggregate(
        total=Sum('amount_invested')
    )['total'] or 0
    return render(request, 'admin_panel/investments.html', {
        'investments':  investments[:100],
        'total_active': total_active,
    })


@login_required
@staff_required
def admin_investment_plans(request):
    from apps.investments.models import InvestmentPlan, InvestmentCategory
    plans      = InvestmentPlan.objects.select_related('category').order_by('category','display_order')
    categories = InvestmentCategory.objects.all()
    return render(request, 'admin_panel/plans.html', {'plans': plans, 'categories': categories})


@login_required
@staff_required
def admin_platform_accounts(request):
    from apps.deposits.models import PlatformBankAccount
    accounts = PlatformBankAccount.objects.all()
    return render(request, 'admin_panel/platform_accounts.html', {'accounts': accounts})


@login_required
@staff_required
def admin_reports(request):
    from apps.investments.models import Investment
    from apps.deposits.models import BankDeposit, CryptoDeposit
    from apps.withdrawals.models import Withdrawal

    stats = {
        'total_deposits_approved': BankDeposit.objects.filter(
            status='APPROVED').aggregate(total=Sum('amount'))['total'] or 0,
        'total_crypto_deposits': CryptoDeposit.objects.filter(
            status='APPROVED').aggregate(total=Sum('zar_amount'))['total'] or 0,
        'total_withdrawals_completed': Withdrawal.objects.filter(
            status='COMPLETED').aggregate(total=Sum('amount'))['total'] or 0,
        'total_invested': Investment.objects.filter(
            status='ACTIVE').aggregate(total=Sum('amount_invested'))['total'] or 0,
        'total_users':    User.objects.filter(is_staff=False).count(),
        'verified_users': User.objects.filter(is_verified=True, is_staff=False).count(),
    }
    return render(request, 'admin_panel/reports.html', {'stats': stats})


# ── WITHDRAWAL CODE MANAGEMENT ────────────────────────────────────

from apps.withdrawals.models import WithdrawalCode


def _get_and_clear_new_code(request):
    pk_hex = request.session.pop('new_wdr_code', None)
    if pk_hex:
        try:
            import uuid
            return WithdrawalCode.objects.get(pk=uuid.UUID(pk_hex))
        except Exception:
            pass
    return None


@login_required
@staff_required
def withdrawal_codes(request):
    status_filter = request.GET.get('status', '')
    codes_qs      = WithdrawalCode.objects.select_related(
        'issued_to','issued_by'
    ).order_by('-created_at')
    if status_filter:
        codes_qs = codes_qs.filter(status=status_filter)

    # Auto-expire overdue codes
    expired_pks = list(
        WithdrawalCode.objects.filter(
            status='ACTIVE', expires_at__lt=timezone.now()
        ).values_list('pk', flat=True)
    )
    if expired_pks:
        WithdrawalCode.objects.filter(pk__in=expired_pks).update(status='EXPIRED')

    stats = {
        'active':  WithdrawalCode.objects.filter(status='ACTIVE').count(),
        'used':    WithdrawalCode.objects.filter(status='USED').count(),
        'expired': WithdrawalCode.objects.filter(status__in=['EXPIRED','REVOKED']).count(),
        'total':   WithdrawalCode.objects.count(),
    }
    return render(request, 'admin_panel/withdrawal_codes.html', {
        'codes':    codes_qs,
        'users':    User.objects.filter(is_active=True).order_by('first_name'),
        'stats':    stats,
        'new_code': _get_and_clear_new_code(request),
    })


@login_required
@staff_required
def generate_withdrawal_code(request):
    if request.method != 'POST':
        return redirect('admin_withdrawal_codes')

    user_id    = request.POST.get('user_id', '').strip()
    max_amount = request.POST.get('max_amount', '').strip()
    expires_at = request.POST.get('expires_at', '').strip()
    notes      = request.POST.get('notes', '').strip()

    try:
        target_user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect('admin_withdrawal_codes')

    from decimal import Decimal, InvalidOperation
    from django.utils.dateparse import parse_datetime

    ma = None
    if max_amount:
        try:
            ma = Decimal(max_amount)
            if ma <= 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            messages.error(request, "Invalid max amount.")
            return redirect('admin_withdrawal_codes')

    ea = None
    if expires_at:
        ea = parse_datetime(expires_at)
        if ea and ea < timezone.now():
            messages.error(request, "Expiry date must be in the future.")
            return redirect('admin_withdrawal_codes')

    code = WithdrawalCode.objects.create(
        code=WithdrawalCode.generate_code(),
        issued_to=target_user,
        issued_by=request.user,
        max_amount=ma,
        expires_at=ea,
        notes=notes,
    )
    request.session['new_wdr_code'] = code.pk.hex
    messages.success(request,
        f"Code {code.code} generated for {target_user.get_full_name()}. "
        "Copy it now — it will not be shown in plaintext again.")
    return redirect('admin_withdrawal_codes')


@login_required
@staff_required
def admin_profile(request):
    """Admin profile — password change only."""
    if request.method == 'POST':
        current = request.POST.get('current_password', '')
        new1    = request.POST.get('new_password1', '')
        new2    = request.POST.get('new_password2', '')

        if not request.user.check_password(current):
            messages.error(request, "Current password is incorrect.")
        elif len(new1) < 8:
            messages.error(request, "New password must be at least 8 characters.")
        elif new1 != new2:
            messages.error(request, "New passwords do not match.")
        else:
            request.user.set_password(new1)
            request.user.save()
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password updated successfully.")
            return redirect('admin_profile')

    return render(request, 'admin_panel/profile.html')


@login_required
@staff_required
def revoke_withdrawal_code(request, pk):
    if request.method == 'POST':
        updated = WithdrawalCode.objects.filter(
            pk=pk, status='ACTIVE'
        ).update(status='REVOKED')
        if updated:
            messages.success(request, "Withdrawal code revoked.")
        else:
            messages.error(request, "Code not found or already inactive.")
    return redirect('admin_withdrawal_codes')


# ── CRYPTO WALLETS ─────────────────────────────────────────────────
@login_required
@staff_required
def admin_crypto_wallets(request):
    from apps.deposits.models import CryptoCurrency
    cryptocurrencies = CryptoCurrency.objects.all().order_by('display_order', 'name')
    return render(request, 'admin_panel/crypto_wallets.html', {'cryptocurrencies': cryptocurrencies})


@login_required
@staff_required
def admin_crypto_wallet_add(request):
    if request.method == 'POST':
        from apps.deposits.models import CryptoCurrency
        name = request.POST.get('name', '').strip()
        symbol = request.POST.get('symbol', '').strip().upper()
        wallet_address = request.POST.get('wallet_address', '').strip()
        network = request.POST.get('network', '').strip()
        minimum_deposit = request.POST.get('minimum_deposit', '0.001')
        display_order = request.POST.get('display_order', '0')
        is_active = request.POST.get('is_active') == 'on'

        if name and symbol and wallet_address:
            try:
                crypto = CryptoCurrency(
                    name=name,
                    symbol=symbol,
                    wallet_address=wallet_address,
                    network=network,
                    minimum_deposit=minimum_deposit,
                    display_order=int(display_order),
                    is_active=is_active,
                )
                if 'logo' in request.FILES:
                    crypto.logo = request.FILES['logo']
                crypto.save()
                messages.success(request, f'{name} ({symbol}) wallet added successfully.')
            except Exception as e:
                messages.error(request, f'Error adding wallet: {e}')
        else:
            messages.error(request, 'Name, symbol and wallet address are required.')
    return redirect('admin_crypto_wallets')


@login_required
@staff_required
def admin_crypto_wallet_edit(request, pk):
    if request.method == 'POST':
        from apps.deposits.models import CryptoCurrency
        try:
            crypto = CryptoCurrency.objects.get(pk=pk)
            crypto.name = request.POST.get('name', crypto.name).strip()
            crypto.symbol = request.POST.get('symbol', crypto.symbol).strip().upper()
            crypto.wallet_address = request.POST.get('wallet_address', crypto.wallet_address).strip()
            crypto.network = request.POST.get('network', '').strip()
            crypto.minimum_deposit = request.POST.get('minimum_deposit', crypto.minimum_deposit)
            crypto.display_order = int(request.POST.get('display_order', crypto.display_order))
            crypto.is_active = request.POST.get('is_active') == 'on'
            if 'logo' in request.FILES:
                crypto.logo = request.FILES['logo']
            crypto.save()
            messages.success(request, f'{crypto.name} updated successfully.')
        except CryptoCurrency.DoesNotExist:
            messages.error(request, 'Cryptocurrency not found.')
        except Exception as e:
            messages.error(request, f'Error updating wallet: {e}')
    return redirect('admin_crypto_wallets')


@login_required
@staff_required
def admin_crypto_wallet_toggle(request, pk):
    if request.method == 'POST':
        from apps.deposits.models import CryptoCurrency
        try:
            crypto = CryptoCurrency.objects.get(pk=pk)
            crypto.is_active = not crypto.is_active
            crypto.save()
            status = 'activated' if crypto.is_active else 'deactivated'
            messages.success(request, f'{crypto.name} {status}.')
        except CryptoCurrency.DoesNotExist:
            messages.error(request, 'Cryptocurrency not found.')
    return redirect('admin_crypto_wallets')
