"""
deposits/views.py — Bank and crypto deposit views
"""
import json
import urllib.request
import urllib.error
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.conf import settings

from .models import BankDeposit, CryptoDeposit, PlatformBankAccount, CryptoCurrency
from .forms import BankDepositForm, BankDepositProofForm


# ── DEPOSIT HOME ──────────────────────────────────────────────────
@login_required
def deposit_home(request):
    bank_deposits   = BankDeposit.objects.filter(user=request.user).order_by('-created_at')[:3]
    crypto_deposits = CryptoDeposit.objects.filter(user=request.user).order_by('-created_at')[:3]
    return render(request, 'deposits/home.html', {
        'bank_deposits':   bank_deposits,
        'crypto_deposits': crypto_deposits,
    })


# ── BANK DEPOSIT ──────────────────────────────────────────────────
@login_required
def bank_deposit_create(request):
    if request.method == 'POST':
        form = BankDepositForm(request.POST)
        if form.is_valid():
            platform_account = PlatformBankAccount.objects.filter(is_active=True).first()
            if not platform_account:
                messages.error(request, "No bank account available right now. Please contact support.")
                return redirect('deposit_home')
            deposit = form.save(commit=False)
            deposit.user = request.user
            deposit.platform_account = platform_account
            deposit.save()
            return redirect('bank_deposit_detail', pk=deposit.pk)
    else:
        form = BankDepositForm()
    return render(request, 'deposits/bank_deposit_create.html', {'form': form})


@login_required
def bank_deposit_detail(request, pk):
    deposit = get_object_or_404(BankDeposit, pk=pk, user=request.user)
    if request.method == 'POST':
        proof_form = BankDepositProofForm(request.POST, request.FILES, instance=deposit)
        if proof_form.is_valid():
            dep = proof_form.save(commit=False)
            dep.status = 'SUBMITTED'
            dep.save()
            messages.success(request, "Proof of payment submitted! We'll verify and credit your account within 1–4 hours.")
            return redirect('deposit_history')
    else:
        proof_form = BankDepositProofForm()
    return render(request, 'deposits/bank_deposit_detail.html', {
        'deposit': deposit, 'proof_form': proof_form,
    })


# ── LIVE PRICE API ────────────────────────────────────────────────
def _fetch_zar_price(symbol: str) -> Decimal | None:
    """
    Fetch live ZAR price for a crypto symbol using CoinGecko free API.
    Falls back to None on any error so the UI can gracefully degrade.
    Coin IDs: BTC=bitcoin, ETH=ethereum, USDT=tether, BNB=binancecoin, SOL=solana
    """
    COIN_ID_MAP = {
        'BTC': 'bitcoin', 'ETH': 'ethereum', 'USDT': 'tether',
        'BNB': 'binancecoin', 'SOL': 'solana', 'XRP': 'ripple',
        'USDC': 'usd-coin', 'ADA': 'cardano', 'DOGE': 'dogecoin',
        'LTC': 'litecoin',
    }
    coin_id = COIN_ID_MAP.get(symbol.upper())
    if not coin_id:
        return None
    try:
        url = (f"https://api.coingecko.com/api/v3/simple/price"
               f"?ids={coin_id}&vs_currencies=zar")
        req = urllib.request.Request(url, headers={'User-Agent': 'InvestZA/1.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            price = data.get(coin_id, {}).get('zar')
            return Decimal(str(price)) if price else None
    except Exception:
        return None


@require_GET
@login_required
def crypto_price_api(request):
    """AJAX endpoint — returns live ZAR price for a given symbol."""
    symbol = request.GET.get('symbol', '').strip().upper()
    if not symbol:
        return JsonResponse({'error': 'No symbol provided'}, status=400)
    try:
        currency = CryptoCurrency.objects.get(symbol__iexact=symbol, is_active=True)
    except CryptoCurrency.DoesNotExist:
        return JsonResponse({'error': 'Currency not found'}, status=404)

    price = _fetch_zar_price(symbol)
    if price is None:
        return JsonResponse({'error': 'Price unavailable', 'symbol': symbol})
    return JsonResponse({
        'symbol':       symbol,
        'name':         currency.name,
        'price_zar':    float(price),
        'network':      currency.network,
        'min_deposit':  float(currency.minimum_deposit),
    })


# ── CRYPTO DEPOSIT CREATE ─────────────────────────────────────────
@login_required
def crypto_deposit_create(request):
    currencies = CryptoCurrency.objects.filter(is_active=True).order_by('display_order', 'name')
    errors = {}

    if request.method == 'POST':
        symbol      = request.POST.get('symbol', '').strip().upper()
        raw_crypto  = request.POST.get('crypto_amount', '').strip()
        raw_zar     = request.POST.get('zar_amount', '').strip()
        raw_rate    = request.POST.get('exchange_rate_used', '').strip()

        # --- Validate fields ---
        try:
            currency = CryptoCurrency.objects.get(symbol__iexact=symbol, is_active=True)
        except CryptoCurrency.DoesNotExist:
            errors['symbol'] = "Please select a valid cryptocurrency."
            currency = None

        crypto_amount = None
        try:
            crypto_amount = Decimal(raw_crypto)
            if crypto_amount <= 0:
                raise ValueError
            if currency and crypto_amount < currency.minimum_deposit:
                errors['crypto_amount'] = f"Minimum deposit is {currency.minimum_deposit} {symbol}."
        except (InvalidOperation, ValueError):
            errors['crypto_amount'] = "Please enter a valid crypto amount."

        zar_amount = None
        try:
            zar_amount = Decimal(raw_zar)
            if zar_amount < Decimal(str(getattr(settings, 'MIN_DEPOSIT', 500))):
                errors['zar_amount'] = f"Minimum ZAR equivalent is R{getattr(settings, 'MIN_DEPOSIT', 500):,.2f}."
        except (InvalidOperation, ValueError):
            errors['zar_amount'] = "Please enter a valid ZAR equivalent."

        exchange_rate = None
        try:
            exchange_rate = Decimal(raw_rate)
            if exchange_rate <= 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            errors['exchange_rate_used'] = "Exchange rate is missing. Please use the calculator."

        if not errors and currency:
            deposit = CryptoDeposit.objects.create(
                user=request.user,
                cryptocurrency=currency,
                crypto_amount=crypto_amount,
                zar_amount=zar_amount,
                exchange_rate_used=exchange_rate,
                status='PENDING',
            )
            return redirect('crypto_deposit_detail', pk=deposit.pk)

    return render(request, 'deposits/crypto_deposit_create.html', {
        'currencies': currencies,
        'errors':     errors,
        'post':       request.POST if request.method == 'POST' else {},
    })


# ── CRYPTO DEPOSIT DETAIL (submit hash) ──────────────────────────
@login_required
def crypto_deposit_detail(request, pk):
    deposit = get_object_or_404(CryptoDeposit, pk=pk, user=request.user)

    error = None
    if request.method == 'POST':
        tx_hash  = request.POST.get('transaction_hash', '').strip()
        from_addr = request.POST.get('from_wallet_address', '').strip()

        if not tx_hash:
            error = "Please enter the transaction hash / TxID."
        elif len(tx_hash) < 20:
            error = "Transaction hash looks too short. Please double-check."
        else:
            deposit.transaction_hash     = tx_hash
            deposit.from_wallet_address  = from_addr
            deposit.status               = 'SUBMITTED'
            deposit.save(update_fields=['transaction_hash', 'from_wallet_address', 'status', 'updated_at'])
            messages.success(request,
                "Transaction submitted! Our team will verify on the blockchain and credit your wallet.")
            return redirect('deposit_history')

    return render(request, 'deposits/crypto_deposit_detail.html', {
        'deposit': deposit, 'error': error,
    })


# ── DEPOSIT HISTORY ───────────────────────────────────────────────
@login_required
def deposit_history(request):
    bank_deposits   = BankDeposit.objects.filter(user=request.user).order_by('-created_at')
    crypto_deposits = CryptoDeposit.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'deposits/history.html', {
        'bank_deposits': bank_deposits, 'crypto_deposits': crypto_deposits,
    })
