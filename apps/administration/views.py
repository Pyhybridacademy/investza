"""
administration/views.py
Admin panel - full management of users, investments, deposits, withdrawals
"""
from django.db import models
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
    from apps.investments.models import Investment, InvestmentPlan
    from django.contrib.auth import get_user_model
    User = get_user_model()

    status_tabs = [
        ('All',       ''),
        ('Active',    'ACTIVE'),
        ('Pending',   'PENDING'),
        ('Matured',   'MATURED'),
        ('Cancelled', 'CANCELLED'),
    ]
    current_status = request.GET.get('status', '')

    qs = Investment.objects.select_related('user', 'plan__category').order_by('-created_at')
    if current_status:
        qs = qs.filter(status=current_status)

    total_active  = Investment.objects.filter(status='ACTIVE').aggregate(total=Sum('amount_invested'))['total'] or 0
    active_count  = Investment.objects.filter(status='ACTIVE').count()
    pending_count = Investment.objects.filter(status='PENDING').count()

    all_users = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
    all_plans = InvestmentPlan.objects.filter(is_active=True).select_related('category').order_by('category', 'display_order')

    return render(request, 'admin_panel/investments.html', {
        'investments':     qs[:200],
        'total_active':    total_active,
        'active_count':    active_count,
        'pending_count':   pending_count,
        'status_tabs':     status_tabs,
        'current_status':  current_status,
        'all_users':       all_users,
        'all_plans':       all_plans,
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


# ── INVESTMENT MANAGEMENT ──────────────────────────────────────────
@login_required
@staff_required
def admin_investment_detail(request, pk):
    """View a single investment with full detail and management actions."""
    from apps.investments.models import Investment
    investment = get_object_or_404(Investment, pk=pk)
    return render(request, 'admin_panel/investment_detail.html', {'investment': investment})


@login_required
@staff_required
def admin_investment_activate(request, pk):
    """Activate a PENDING investment."""
    if request.method != 'POST':
        return redirect('admin_investments')
    from apps.investments.models import Investment
    investment = get_object_or_404(Investment, pk=pk)
    if investment.status == 'PENDING':
        investment.activate()
        messages.success(request, f'Investment {investment.reference} activated.')
    else:
        messages.error(request, 'Only PENDING investments can be activated.')
    return redirect('admin_investment_detail', pk=pk)


@login_required
@staff_required
def admin_investment_cancel(request, pk):
    """Cancel an investment and refund the user's wallet."""
    if request.method != 'POST':
        return redirect('admin_investments')
    from apps.investments.models import Investment
    from apps.accounts.models import Wallet
    from decimal import Decimal
    from django.db import transaction as db_transaction

    investment = get_object_or_404(Investment, pk=pk)
    if investment.status not in ('PENDING', 'ACTIVE'):
        messages.error(request, 'Only PENDING or ACTIVE investments can be cancelled.')
        return redirect('admin_investment_detail', pk=pk)

    reason = request.POST.get('reason', 'Cancelled by admin').strip() or 'Cancelled by admin'

    with db_transaction.atomic():
        wallet = investment.user.get_wallet()
        refund = investment.amount_invested

        # Return capital to available balance
        wallet.credit(refund, f'Investment cancelled — refund: {investment.reference}')

        # Remove from invested balance (if it was active)
        if investment.status == 'ACTIVE':
            Wallet.objects.filter(pk=wallet.pk).update(
                invested_balance=models.F('invested_balance') - refund
            )

        investment.status = 'CANCELLED'
        investment.save(update_fields=['status', 'updated_at'])

    messages.success(request, f'Investment {investment.reference} cancelled. R{refund:,.2f} refunded to user.')
    return redirect('admin_investment_detail', pk=pk)


@login_required
@staff_required
def admin_investment_complete(request, pk):
    """Manually mark an investment as matured and pay out ROI + principal."""
    if request.method != 'POST':
        return redirect('admin_investments')
    from apps.investments.models import Investment, ROIPayment
    from apps.accounts.models import Wallet
    from decimal import Decimal
    from django.db import transaction as db_transaction

    investment = get_object_or_404(Investment, pk=pk)
    if investment.status != 'ACTIVE':
        messages.error(request, 'Only ACTIVE investments can be completed.')
        return redirect('admin_investment_detail', pk=pk)

    with db_transaction.atomic():
        wallet = investment.user.get_wallet()
        roi = investment.expected_roi

        # Pay ROI to wallet
        wallet.credit(roi, f'ROI payout — {investment.reference}')

        # Track ROI payment
        ROIPayment.objects.create(
            investment=investment,
            amount=roi,
            notes='Manual payout by admin'
        )

        # Return principal if plan says so
        if investment.plan.returns_principal:
            Wallet.objects.filter(pk=wallet.pk).update(
                invested_balance=models.F('invested_balance') - investment.amount_invested
            )

        # Update investment totals
        investment.actual_roi_paid = roi
        investment.status = 'MATURED'
        from django.utils import timezone
        investment.completed_at = timezone.now()
        investment.save(update_fields=['actual_roi_paid', 'status', 'completed_at', 'updated_at'])

        # Update total_earned on wallet
        Wallet.objects.filter(pk=wallet.pk).update(
            total_earned=models.F('total_earned') + roi
        )

    messages.success(request, f'Investment {investment.reference} completed. R{roi:,.2f} ROI paid to user.')
    return redirect('admin_investment_detail', pk=pk)


@login_required
@staff_required
def admin_investment_adjust(request, pk):
    """Adjust the investment amount or expected ROI manually."""
    if request.method != 'POST':
        return redirect('admin_investments')
    from apps.investments.models import Investment
    from decimal import Decimal, InvalidOperation

    investment = get_object_or_404(Investment, pk=pk)
    try:
        new_amount = request.POST.get('amount_invested', '').strip()
        new_roi = request.POST.get('expected_roi', '').strip()
        notes = request.POST.get('notes', 'Admin adjustment').strip()

        changed = []
        if new_amount:
            investment.amount_invested = Decimal(new_amount)
            investment.expected_total = investment.plan.calculate_total_return(investment.amount_invested)
            changed.append('amount')
        if new_roi:
            investment.expected_roi = Decimal(new_roi)
            investment.expected_total = investment.amount_invested + investment.expected_roi
            changed.append('ROI')
        if changed:
            investment.save()
            messages.success(request, f'Investment {investment.reference} updated: {", ".join(changed)} adjusted.')
        else:
            messages.warning(request, 'No changes submitted.')
    except (InvalidOperation, ValueError) as e:
        messages.error(request, f'Invalid value: {e}')
    return redirect('admin_investment_detail', pk=pk)


@login_required
@staff_required
def admin_investment_create(request):
    """Admin creates an investment on behalf of a user."""
    if request.method == 'POST':
        from apps.investments.models import Investment, InvestmentPlan
        from apps.accounts.models import Wallet
        from decimal import Decimal, InvalidOperation
        from django.db import transaction as db_transaction
        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user_id   = request.POST.get('user_id')
            plan_id   = request.POST.get('plan_id')
            amount    = Decimal(request.POST.get('amount', '0'))
            activate  = request.POST.get('activate') == 'on'

            user = get_object_or_404(User, pk=user_id)
            plan = get_object_or_404(InvestmentPlan, pk=plan_id)

            if amount < plan.minimum_amount:
                messages.error(request, f'Amount below minimum (R{plan.minimum_amount:,.2f}).')
                return redirect('admin_investments')
            if amount > plan.maximum_amount:
                messages.error(request, f'Amount above maximum (R{plan.maximum_amount:,.2f}).')
                return redirect('admin_investments')

            with db_transaction.atomic():
                investment = Investment(
                    user=user,
                    plan=plan,
                    amount_invested=amount,
                    expected_roi=plan.calculate_roi(amount),
                    expected_total=plan.calculate_total_return(amount),
                )
                investment.save()

                if activate:
                    # Debit wallet and move to invested balance
                    wallet = user.get_wallet()
                    wallet.debit(amount, f'Investment in {plan.name} — Ref: {investment.reference} (admin)')
                    Wallet.objects.filter(pk=wallet.pk).update(
                        invested_balance=models.F('invested_balance') + amount
                    )
                    investment.activate()

            messages.success(request, f'Investment {investment.reference} created for {user.get_full_name()}.')
            return redirect('admin_investment_detail', pk=investment.pk)

        except (InvalidOperation, ValueError) as e:
            messages.error(request, f'Error: {e}')
    return redirect('admin_investments')


# ═══════════════════════════════════════════════════════════════════════════
#  PLATFORM SETTINGS
# ═══════════════════════════════════════════════════════════════════════════

@login_required
@staff_required
def admin_platform_settings(request):
    from apps.accounts.models import PlatformSettings
    ps = PlatformSettings.get()

    if request.method == 'POST':
        ps.platform_name       = request.POST.get('platform_name', ps.platform_name).strip()
        ps.tagline             = request.POST.get('tagline', ps.tagline).strip()
        ps.support_email       = request.POST.get('support_email', ps.support_email).strip()
        ps.support_phone       = request.POST.get('support_phone', ps.support_phone).strip()
        ps.support_whatsapp    = request.POST.get('support_whatsapp', '').strip()
        ps.website_url         = request.POST.get('website_url', '').strip()
        ps.fsp_number          = request.POST.get('fsp_number', '').strip()
        ps.registered_address  = request.POST.get('registered_address', '').strip()
        ps.currency_code       = request.POST.get('currency_code', ps.currency_code).strip()
        ps.currency_symbol     = request.POST.get('currency_symbol', ps.currency_symbol).strip()
        ps.twitter_url         = request.POST.get('twitter_url', '').strip()
        ps.linkedin_url        = request.POST.get('linkedin_url', '').strip()
        ps.facebook_url        = request.POST.get('facebook_url', '').strip()
        ps.instagram_url       = request.POST.get('instagram_url', '').strip()
        ps.maintenance_mode    = request.POST.get('maintenance_mode') == 'on'
        ps.maintenance_message = request.POST.get('maintenance_message', ps.maintenance_message).strip()

        from decimal import Decimal, InvalidOperation
        for field in ['min_deposit', 'max_deposit', 'min_withdrawal', 'max_withdrawal', 'withdrawal_fee_pct']:
            val = request.POST.get(field, '')
            if val:
                try:
                    setattr(ps, field, Decimal(val))
                except InvalidOperation:
                    pass

        ps.updated_by = request.user
        ps.save()
        # Immediately bust the maintenance-mode cache so the change takes effect
        from apps.accounts.middleware import invalidate_maintenance_cache
        invalidate_maintenance_cache()
        messages.success(request, 'Platform settings updated successfully.')
        return redirect('admin_platform_settings')

    return render(request, 'admin_panel/platform_settings.html', {'ps': ps})


# ═══════════════════════════════════════════════════════════════════════════
#  PLATFORM BANK ACCOUNTS (full CRUD in custom admin)
# ═══════════════════════════════════════════════════════════════════════════

@login_required
@staff_required
def admin_platform_accounts(request):
    from apps.deposits.models import PlatformBankAccount
    accounts = PlatformBankAccount.objects.all().order_by('is_active', 'bank_name')
    return render(request, 'admin_panel/platform_accounts.html', {'accounts': accounts})


@login_required
@staff_required
def admin_bank_account_create(request):
    from apps.deposits.models import PlatformBankAccount
    if request.method == 'POST':
        PlatformBankAccount.objects.create(
            bank_name       = request.POST.get('bank_name', '').strip(),
            account_holder  = request.POST.get('account_holder', '').strip(),
            account_number  = request.POST.get('account_number', '').strip(),
            account_type    = request.POST.get('account_type', 'Cheque').strip(),
            branch_code     = request.POST.get('branch_code', '').strip(),
            branch_name     = request.POST.get('branch_name', '').strip(),
            swift_code      = request.POST.get('swift_code', '').strip(),
            reference_prefix= request.POST.get('reference_prefix', 'INZ').strip(),
            is_active       = request.POST.get('is_active') == 'on',
        )
        messages.success(request, 'Bank account added successfully.')
        return redirect('admin_platform_accounts')
    from apps.deposits.models import PlatformBankAccount
    return render(request, 'admin_panel/bank_account_form.html', {
        'bank_choices': PlatformBankAccount.BANK_CHOICES,
        'action': 'Add',
    })


@login_required
@staff_required
def admin_bank_account_edit(request, pk):
    from apps.deposits.models import PlatformBankAccount
    acc = get_object_or_404(PlatformBankAccount, pk=pk)
    if request.method == 'POST':
        acc.bank_name        = request.POST.get('bank_name', acc.bank_name).strip()
        acc.account_holder   = request.POST.get('account_holder', acc.account_holder).strip()
        acc.account_number   = request.POST.get('account_number', acc.account_number).strip()
        acc.account_type     = request.POST.get('account_type', acc.account_type).strip()
        acc.branch_code      = request.POST.get('branch_code', acc.branch_code).strip()
        acc.branch_name      = request.POST.get('branch_name', '').strip()
        acc.swift_code       = request.POST.get('swift_code', '').strip()
        acc.reference_prefix = request.POST.get('reference_prefix', acc.reference_prefix).strip()
        acc.is_active        = request.POST.get('is_active') == 'on'
        acc.save()
        messages.success(request, 'Bank account updated.')
        return redirect('admin_platform_accounts')
    return render(request, 'admin_panel/bank_account_form.html', {
        'acc': acc,
        'bank_choices': PlatformBankAccount.BANK_CHOICES,
        'action': 'Edit',
    })


@login_required
@staff_required
def admin_bank_account_toggle(request, pk):
    from apps.deposits.models import PlatformBankAccount
    acc = get_object_or_404(PlatformBankAccount, pk=pk)
    acc.is_active = not acc.is_active
    acc.save()
    state = 'activated' if acc.is_active else 'deactivated'
    messages.success(request, f'{acc} has been {state}.')
    return redirect('admin_platform_accounts')


@login_required
@staff_required
def admin_bank_account_delete(request, pk):
    from apps.deposits.models import PlatformBankAccount
    acc = get_object_or_404(PlatformBankAccount, pk=pk)
    if request.method == 'POST':
        acc.delete()
        messages.success(request, 'Bank account deleted.')
    return redirect('admin_platform_accounts')


# ═══════════════════════════════════════════════════════════════════════════
#  INVESTMENT PLANS (full CRUD in custom admin)
# ═══════════════════════════════════════════════════════════════════════════

@login_required
@staff_required
def admin_investment_plans(request):
    from apps.investments.models import InvestmentPlan, InvestmentCategory
    plans      = InvestmentPlan.objects.select_related('category').order_by('category', 'display_order')
    categories = InvestmentCategory.objects.all()
    return render(request, 'admin_panel/plans.html', {'plans': plans, 'categories': categories})


@login_required
@staff_required
def admin_plan_create(request):
    from apps.investments.models import InvestmentPlan, InvestmentCategory
    from decimal import Decimal, InvalidOperation
    categories = InvestmentCategory.objects.filter(is_active=True)
    if request.method == 'POST':
        try:
            cat = get_object_or_404(InvestmentCategory, pk=request.POST.get('category'))
            plan = InvestmentPlan(
                category         = cat,
                name             = request.POST.get('name', '').strip(),
                description      = request.POST.get('description', '').strip(),
                minimum_amount   = Decimal(request.POST.get('minimum_amount', '500')),
                maximum_amount   = Decimal(request.POST.get('maximum_amount', '1000000')),
                duration_value   = int(request.POST.get('duration_value', 30)),
                duration_unit    = request.POST.get('duration_unit', 'DAYS'),
                roi_type         = request.POST.get('roi_type', 'FIXED'),
                roi_percentage   = Decimal(request.POST.get('roi_percentage', '10')),
                returns_principal= request.POST.get('returns_principal') == 'on',
                is_active        = request.POST.get('is_active') == 'on',
                is_featured      = request.POST.get('is_featured') == 'on',
                display_order    = int(request.POST.get('display_order', 0)),
            )
            plan.save()
            messages.success(request, f'Plan "{plan.name}" created.')
            return redirect('admin_investment_plans')
        except (InvalidOperation, ValueError) as e:
            messages.error(request, f'Error: {e}')
    return render(request, 'admin_panel/plan_form.html', {
        'categories': categories,
        'duration_units': InvestmentPlan.DURATION_UNITS,
        'roi_types': InvestmentPlan.ROI_TYPES,
        'action': 'Create',
    })


@login_required
@staff_required
def admin_plan_edit(request, pk):
    from apps.investments.models import InvestmentPlan, InvestmentCategory
    from decimal import Decimal, InvalidOperation
    plan       = get_object_or_404(InvestmentPlan, pk=pk)
    categories = InvestmentCategory.objects.filter(is_active=True)
    if request.method == 'POST':
        try:
            plan.category         = get_object_or_404(InvestmentCategory, pk=request.POST.get('category'))
            plan.name             = request.POST.get('name', plan.name).strip()
            plan.description      = request.POST.get('description', plan.description).strip()
            plan.minimum_amount   = Decimal(request.POST.get('minimum_amount', plan.minimum_amount))
            plan.maximum_amount   = Decimal(request.POST.get('maximum_amount', plan.maximum_amount))
            plan.duration_value   = int(request.POST.get('duration_value', plan.duration_value))
            plan.duration_unit    = request.POST.get('duration_unit', plan.duration_unit)
            plan.roi_type         = request.POST.get('roi_type', plan.roi_type)
            plan.roi_percentage   = Decimal(request.POST.get('roi_percentage', plan.roi_percentage))
            plan.returns_principal= request.POST.get('returns_principal') == 'on'
            plan.is_active        = request.POST.get('is_active') == 'on'
            plan.is_featured      = request.POST.get('is_featured') == 'on'
            plan.display_order    = int(request.POST.get('display_order', plan.display_order))
            plan.save()
            messages.success(request, f'Plan "{plan.name}" updated.')
            return redirect('admin_investment_plans')
        except (InvalidOperation, ValueError) as e:
            messages.error(request, f'Error: {e}')
    return render(request, 'admin_panel/plan_form.html', {
        'plan': plan,
        'categories': categories,
        'duration_units': InvestmentPlan.DURATION_UNITS,
        'roi_types': InvestmentPlan.ROI_TYPES,
        'action': 'Edit',
    })


@login_required
@staff_required
def admin_plan_toggle(request, pk):
    from apps.investments.models import InvestmentPlan
    plan = get_object_or_404(InvestmentPlan, pk=pk)
    plan.is_active = not plan.is_active
    plan.save()
    messages.success(request, f'"{plan.name}" {"activated" if plan.is_active else "deactivated"}.')
    return redirect('admin_investment_plans')


@login_required
@staff_required
def admin_plan_delete(request, pk):
    from apps.investments.models import InvestmentPlan
    plan = get_object_or_404(InvestmentPlan, pk=pk)
    if request.method == 'POST':
        if plan.investments.filter(status__in=['ACTIVE','PENDING']).exists():
            messages.error(request, 'Cannot delete a plan with active investments.')
        else:
            name = plan.name
            plan.delete()
            messages.success(request, f'Plan "{name}" deleted.')
    return redirect('admin_investment_plans')
