"""
withdrawals/views.py — 3-step verification flow
Step 1: amount + method | Step 2: withdrawal code | Step 3: tax code + PDF
"""
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models as db_models
from django.http import HttpResponse, Http404

from apps.accounts.models import BankAccount, WalletTransaction, Wallet
from apps.deposits.models import CryptoCurrency
from .models import Withdrawal, WithdrawalCode
from .tax_pdf import generate_tax_certificate


def _validate_amount(raw, wallet):
    try:
        amount = Decimal(raw or '0')
    except InvalidOperation:
        return None, "Please enter a valid amount."
    min_wd = Decimal(str(settings.MIN_WITHDRAWAL))
    if amount <= 0:
        return None, "Amount must be greater than zero."
    if amount < min_wd:
        return None, f"Minimum withdrawal is R{min_wd:,.2f}."
    wallet.refresh_from_db()
    if amount > wallet.available_balance:
        return None, f"Insufficient balance. Available: R{wallet.available_balance:,.2f}."
    return amount, None


def _clear_session(request):
    for key in ['wdr_amount','wdr_method','wdr_notes','wdr_bank_id',
                'wdr_crypto_id','wdr_crypto_addr','wdr_code_id']:
        request.session.pop(key, None)


# ── HOME ──────────────────────────────────────────────────────────
@login_required
def withdrawal_home(request):
    wallet = request.user.get_wallet()
    context = {
        'wallet': wallet,
        'bank_accounts': BankAccount.objects.filter(user=request.user),
        'crypto_currencies': CryptoCurrency.objects.filter(is_active=True),
        'recent_withdrawals': Withdrawal.objects.filter(user=request.user).order_by('-created_at')[:5],
        'min_withdrawal': settings.MIN_WITHDRAWAL,
    }
    return render(request, 'withdrawals/home.html', context)


# ── STEP 1 ────────────────────────────────────────────────────────
@login_required
def create_withdrawal(request):
    if request.method != 'POST':
        return redirect('withdrawal_home')
    wallet = Wallet.objects.get(user=request.user)
    amount, err = _validate_amount(request.POST.get('amount'), wallet)
    if err:
        messages.error(request, err)
        return redirect('withdrawal_home')
    method = request.POST.get('method', 'BANK')
    if method == 'BANK':
        bank_id = request.POST.get('bank_account', '')
        if not bank_id or not BankAccount.objects.filter(pk=bank_id, user=request.user).exists():
            messages.error(request, "Please select a valid bank account.")
            return redirect('withdrawal_home')
        request.session['wdr_bank_id'] = str(bank_id)
        request.session['wdr_crypto_id'] = ''
        request.session['wdr_crypto_addr'] = ''
    elif method == 'CRYPTO':
        crypto_id = request.POST.get('cryptocurrency', '')
        crypto_addr = request.POST.get('crypto_wallet_address', '').strip()
        if not crypto_id or not crypto_addr:
            messages.error(request, "Please provide cryptocurrency and wallet address.")
            return redirect('withdrawal_home')
        if not CryptoCurrency.objects.filter(pk=crypto_id, is_active=True).exists():
            messages.error(request, "Invalid cryptocurrency.")
            return redirect('withdrawal_home')
        request.session['wdr_bank_id'] = ''
        request.session['wdr_crypto_id'] = str(crypto_id)
        request.session['wdr_crypto_addr'] = crypto_addr
    request.session['wdr_amount'] = str(amount)
    request.session['wdr_method'] = method
    request.session['wdr_notes'] = request.POST.get('user_notes', '')
    return redirect('withdrawal_step2')


# ── STEP 2: WITHDRAWAL CODE ───────────────────────────────────────
@login_required
def withdrawal_step2(request):
    if 'wdr_amount' not in request.session:
        messages.error(request, "Session expired. Please start again.")
        return redirect('withdrawal_home')
    amount = Decimal(request.session['wdr_amount'])
    error = None
    if request.method == 'POST':
        code_str = request.POST.get('withdrawal_code', '').strip().upper()
        if not code_str:
            error = "Please enter your withdrawal authorisation code."
        else:
            try:
                code_obj = WithdrawalCode.objects.get(code=code_str, issued_to=request.user)
                valid, reason = code_obj.is_valid(amount)
                if not valid:
                    error = reason
                else:
                    request.session['wdr_code_id'] = str(code_obj.pk)
                    return redirect('withdrawal_step3')
            except WithdrawalCode.DoesNotExist:
                error = "Invalid withdrawal code. Please check the code and try again."
    return render(request, 'withdrawals/step2_code.html', {'amount': amount, 'error': error})


# ── STEP 3: TAX CODE + PDF + SUBMIT ──────────────────────────────
@login_required
def withdrawal_step3(request):
    if 'wdr_amount' not in request.session or 'wdr_code_id' not in request.session:
        messages.error(request, "Session expired. Please start again.")
        return redirect('withdrawal_home')
    amount = Decimal(request.session['wdr_amount'])
    error = None
    if request.method == 'POST':
        import re
        tax_code = request.POST.get('tax_code', '').strip().upper()
        if not tax_code:
            error = "Please enter your SARS tax clearance code."
        elif not re.match(r'^[A-Z0-9\-]{6,30}$', tax_code):
            error = "Tax code format is invalid. It should contain only letters, numbers and hyphens (6–30 characters)."
        else:
            wallet = Wallet.objects.get(user=request.user)
            wallet.refresh_from_db()
            if amount > wallet.available_balance:
                messages.error(request, "Insufficient balance. Please start a new withdrawal.")
                _clear_session(request)
                return redirect('withdrawal_home')
            method  = request.session['wdr_method']
            notes   = request.session.get('wdr_notes', '')
            code_pk = request.session['wdr_code_id']
            wd = Withdrawal(
                user=request.user, amount=amount, method=method, user_notes=notes,
                fee=Decimal('0.00'), net_amount=amount,
                withdrawal_code_used=True, tax_code=tax_code, tax_certificate_issued=True,
            )
            if method == 'BANK':
                wd.bank_account = BankAccount.objects.get(pk=request.session['wdr_bank_id'], user=request.user)
            elif method == 'CRYPTO':
                wd.crypto_currency = CryptoCurrency.objects.get(pk=request.session['wdr_crypto_id'])
                wd.crypto_wallet_address = request.session['wdr_crypto_addr']
            wd.save()
            # Generate and attach tax PDF
            pdf_bytes = generate_tax_certificate(wd)
            wd.tax_pdf.save(f"tax_cert_{wd.reference}.pdf", ContentFile(pdf_bytes), save=True)
            # Mark withdrawal code as used
            try:
                WithdrawalCode.objects.get(pk=code_pk, issued_to=request.user).mark_used()
            except WithdrawalCode.DoesNotExist:
                pass
            # Deduct balance atomically
            Wallet.objects.filter(pk=wallet.pk).update(
                available_balance=db_models.F('available_balance') - amount,
                pending_withdrawal=db_models.F('pending_withdrawal') + amount,
            )
            wallet.refresh_from_db()
            WalletTransaction.objects.create(
                wallet=wallet, transaction_type='WITHDRAWAL', amount=amount,
                description=f"Withdrawal submitted — Ref: {wd.reference}",
                balance_after=wallet.available_balance,
            )
            _clear_session(request)
            messages.success(request,
                f"Withdrawal of R{amount:,.2f} submitted! Ref: {wd.reference}. "
                "Your tax certificate is ready.")
            return redirect('withdrawal_complete', pk=wd.pk)
    return render(request, 'withdrawals/step3_tax.html', {'amount': amount, 'error': error})


# ── COMPLETE ──────────────────────────────────────────────────────
@login_required
def withdrawal_complete(request, pk):
    wd = get_object_or_404(Withdrawal, pk=pk, user=request.user)
    return render(request, 'withdrawals/complete.html', {'withdrawal': wd})


@login_required
def download_tax_certificate(request, pk):
    wd = get_object_or_404(Withdrawal, pk=pk, user=request.user)
    if not wd.tax_pdf:
        raise Http404("Tax certificate not found.")
    response = HttpResponse(wd.tax_pdf.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="InvestZA_Tax_Cert_{wd.reference}.pdf"'
    return response


# ── HISTORY & DETAIL ─────────────────────────────────────────────
@login_required
def withdrawal_history(request):
    withdrawals = Withdrawal.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'withdrawals/history.html', {'withdrawals': withdrawals})


@login_required
def withdrawal_detail(request, pk):
    withdrawal = get_object_or_404(Withdrawal, pk=pk, user=request.user)
    return render(request, 'withdrawals/detail.html', {'withdrawal': withdrawal})
