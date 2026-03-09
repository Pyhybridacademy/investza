"""
accounts/views.py
Authentication, Dashboard, and Profile views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta

from .forms import UserRegistrationForm, LoginForm, ProfileUpdateForm, BankAccountForm, KYCDocumentForm
from .models import BankAccount, KYCDocument, WalletTransaction

User = get_user_model()


# ─── PUBLIC VIEWS ─────────────────────────────────────────────────────────────

def home(request):
    """Public landing page."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'public/home.html')


def about(request):
    return render(request, 'public/about.html')


def terms(request):
    return render(request, 'public/terms.html')


def privacy(request):
    return render(request, 'public/privacy.html')


def risk_disclosure(request):
    return render(request, 'public/risk_disclosure.html')


def contact(request):
    if request.method == 'POST':
        # Basic contact form — in production, send email via send_contact_email
        from django.contrib import messages as msg
        full_name = request.POST.get('full_name', '').strip()
        email_addr = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        if full_name and email_addr and message:
            # Log it and optionally email support
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Contact form: {full_name} <{email_addr}> — {subject}")
            from django.contrib import messages
            messages.success(request, f"Thank you {full_name}! Your message has been received. We'll respond within 24 hours.")
        else:
            from django.contrib import messages
            messages.error(request, "Please fill in all required fields.")
        return redirect('contact')
    return render(request, 'public/contact.html')


def investment_plans_public(request):
    from apps.investments.models import InvestmentCategory
    categories = InvestmentCategory.objects.filter(is_active=True).prefetch_related('plans')
    return render(request, 'public/plans.html', {'categories': categories})


# ─── AUTH VIEWS ───────────────────────────────────────────────────────────────

def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            from apps.accounts.emails import send_welcome_email
            send_welcome_email(user, request)
            messages.success(request, f"Welcome to InvestZA, {user.first_name}! Your account has been created.")
            return redirect('dashboard')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.GET.get('next', 'dashboard')
            messages.success(request, f"Welcome back, {user.first_name}!")
            return redirect(next_url)
        else:
            messages.error(request, "Invalid email or password.")
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def user_logout(request):
    logout(request)
    messages.info(request, "You have been logged out securely.")
    return redirect('home')


# ─── DASHBOARD VIEWS ──────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    """Main user dashboard."""
    user = request.user
    wallet = user.get_wallet()

    # Recent investments
    from apps.investments.models import Investment
    active_investments = Investment.objects.filter(
        user=user, status='ACTIVE'
    ).select_related('plan__category')[:5]

    # Recent transactions
    recent_transactions = WalletTransaction.objects.filter(
        wallet=wallet
    ).order_by('-created_at')[:10]

    # Stats
    total_invested = Investment.objects.filter(
        user=user, status__in=['ACTIVE', 'MATURED']
    ).aggregate(total=Sum('amount_invested'))['total'] or 0

    total_earned = Investment.objects.filter(
        user=user, status='MATURED'
    ).aggregate(total=Sum('actual_roi_paid'))['total'] or 0

    # Pending items
    from apps.deposits.models import BankDeposit, CryptoDeposit
    from apps.withdrawals.models import Withdrawal
    pending_deposits = BankDeposit.objects.filter(
        user=user, status__in=['PENDING', 'SUBMITTED', 'VERIFYING']
    ).count()
    pending_withdrawals = Withdrawal.objects.filter(
        user=user, status__in=['PENDING', 'PROCESSING']
    ).count()

    context = {
        'wallet': wallet,
        'active_investments': active_investments,
        'recent_transactions': recent_transactions,
        'total_invested': total_invested,
        'total_earned': total_earned,
        'pending_deposits': pending_deposits,
        'pending_withdrawals': pending_withdrawals,
    }
    return render(request, 'dashboard/index.html', context)


@login_required
def profile(request):
    """User profile management — personal info + password change."""
    from django.contrib.auth import update_session_auth_hash
    from apps.investments.models import Investment
    from apps.deposits.models import BankDeposit, CryptoDeposit
    from apps.withdrawals.models import Withdrawal

    user = request.user
    wallet = user.get_wallet()

    # Which form was submitted?
    action = request.POST.get('action', '') if request.method == 'POST' else ''

    # ── Personal info update ──
    if action == 'update_profile':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ProfileUpdateForm(instance=user)

    # ── Password change ──
    pwd_errors = []
    if action == 'change_password':
        current = request.POST.get('current_password', '')
        new1    = request.POST.get('new_password1', '')
        new2    = request.POST.get('new_password2', '')

        if not user.check_password(current):
            pwd_errors.append("Current password is incorrect.")
        elif len(new1) < 8:
            pwd_errors.append("New password must be at least 8 characters.")
        elif new1 != new2:
            pwd_errors.append("New passwords do not match.")
        else:
            user.set_password(new1)
            user.save()
            update_session_auth_hash(request, user)   # keep session alive
            from apps.accounts.emails import send_password_changed_email
            send_password_changed_email(user, request)
            messages.success(request, "Password changed successfully. A confirmation email has been sent.")
            return redirect('profile')

    # ── Summary stats ──
    total_investments = Investment.objects.filter(user=user).count()
    active_investments = Investment.objects.filter(user=user, status='ACTIVE').count()
    total_deposited = (
        BankDeposit.objects.filter(user=user, status='APPROVED').aggregate(
            t=models.Sum('amount'))['t'] or 0
    ) + (
        CryptoDeposit.objects.filter(user=user, status='APPROVED').aggregate(
            t=models.Sum('zar_amount'))['t'] or 0
    )
    total_withdrawn = Withdrawal.objects.filter(
        user=user, status='COMPLETED'
    ).aggregate(t=models.Sum('amount'))['t'] or 0

    context = {
        'form': form,
        'wallet': wallet,
        'pwd_errors': pwd_errors,
        'total_investments': total_investments,
        'active_investments': active_investments,
        'total_deposited': total_deposited,
        'total_withdrawn': total_withdrawn,
    }
    return render(request, 'dashboard/profile.html', context)


@login_required
def bank_accounts(request):
    """Manage user bank accounts."""
    accounts = BankAccount.objects.filter(user=request.user)

    if request.method == 'POST':
        form = BankAccountForm(request.POST)
        if form.is_valid():
            bank_acc = form.save(commit=False)
            bank_acc.user = request.user
            bank_acc.save()
            messages.success(request, "Bank account added successfully.")
            return redirect('bank_accounts')
    else:
        form = BankAccountForm()

    return render(request, 'dashboard/bank_accounts.html', {
        'bank_accounts': accounts,
        'form': form
    })


@login_required
def delete_bank_account(request, pk):
    account = get_object_or_404(BankAccount, pk=pk, user=request.user)
    account.delete()
    messages.success(request, "Bank account removed.")
    return redirect('bank_accounts')


@login_required
def kyc_verification(request):
    """KYC document upload."""
    documents = KYCDocument.objects.filter(user=request.user)

    if request.method == 'POST':
        form = KYCDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.user = request.user
            doc.save()
            messages.success(request, "Document submitted for verification.")
            return redirect('kyc_verification')
    else:
        form = KYCDocumentForm()

    return render(request, 'dashboard/kyc.html', {
        'documents': documents,
        'form': form
    })


@login_required
def transaction_history(request):
    """Full transaction history."""
    wallet = request.user.get_wallet()
    transactions = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')

    return render(request, 'dashboard/transactions.html', {
        'transactions': transactions,
        'wallet': wallet
    })


# ─── PASSWORD RESET VIEWS ─────────────────────────────────────────────────────

def password_reset_request(request):
    """Step 1 — user submits their email address."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        if email:
            try:
                user = User.objects.get(email__iexact=email, is_active=True)
                _send_reset_email(user, request)
            except User.DoesNotExist:
                pass  # Silently succeed — don't reveal whether email exists
        # Always redirect to "sent" page regardless of whether email exists
        return redirect('password_reset_sent')

    return render(request, 'accounts/password_reset_request.html')


def password_reset_sent(request):
    """Step 2 — confirmation page shown after email is sent."""
    return render(request, 'accounts/password_reset_sent.html')


def password_reset_confirm(request, uidb64, token):
    """Step 3 — user clicks link and sets new password."""
    from django.utils.http import urlsafe_base64_decode
    from django.utils.encoding import force_str
    from django.contrib.auth.tokens import default_token_generator

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    token_valid = user is not None and default_token_generator.check_token(user, token)

    if request.method == 'POST' and token_valid:
        password1 = request.POST.get('new_password1', '')
        password2 = request.POST.get('new_password2', '')

        if len(password1) < 8:
            messages.error(request, "Password must be at least 8 characters.")
        elif password1 != password2:
            messages.error(request, "Passwords do not match.")
        else:
            user.set_password(password1)
            user.save()
            # Send confirmation email
            from apps.accounts.emails import send_password_changed_email
            send_password_changed_email(user, request)
            return redirect('password_reset_complete')

    context = {
        'token_valid': token_valid,
        'uidb64': uidb64,
        'token': token,
    }
    return render(request, 'accounts/password_reset_confirm.html', context)


def password_reset_complete(request):
    """Step 4 — success page after password is changed."""
    return render(request, 'accounts/password_reset_complete.html')


def _send_reset_email(user, request):
    """Build the signed reset URL and fire the email."""
    from django.utils.http import urlsafe_base64_encode
    from django.utils.encoding import force_bytes
    from django.contrib.auth.tokens import default_token_generator
    from django.urls import reverse
    from apps.accounts.emails import send_password_reset_email

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_path = reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
    reset_url = request.build_absolute_uri(reset_path)
    send_password_reset_email(user, reset_url)


# ─── PASSWORD CHANGE (logged-in users) ────────────────────────────────────────

@login_required
def password_change(request):
    """Allow logged-in users to change their password."""
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password1 = request.POST.get('new_password1', '')
        new_password2 = request.POST.get('new_password2', '')

        if not request.user.check_password(current_password):
            messages.error(request, "Current password is incorrect.")
        elif len(new_password1) < 8:
            messages.error(request, "New password must be at least 8 characters.")
        elif new_password1 != new_password2:
            messages.error(request, "New passwords do not match.")
        else:
            request.user.set_password(new_password1)
            request.user.save()
            # Re-authenticate so the session stays alive
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            # Send confirmation email
            from apps.accounts.emails import send_password_changed_email
            send_password_changed_email(request.user, request)
            messages.success(request, "Password changed successfully.")
            return redirect('profile')

    return render(request, 'accounts/password_change.html')
