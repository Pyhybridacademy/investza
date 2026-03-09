"""
deposits/views.py — Bank and crypto deposit views
"""
import json
import time
import threading
import urllib.request
import urllib.error
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.conf import settings

# ── IN-MEMORY PRICE CACHE ─────────────────────────────────────────
# Stores {symbol: (price_zar, timestamp)}
# Prices are considered fresh for 90 seconds to reduce API calls
_price_cache: dict = {}
_price_cache_lock = threading.Lock()
CACHE_TTL = 90  # seconds

def _cache_get(symbol: str):
    with _price_cache_lock:
        entry = _price_cache.get(symbol)
        if entry and (time.time() - entry[1]) < CACHE_TTL:
            return entry[0]
    return None

def _cache_set(symbol: str, price):
    with _price_cache_lock:
        _price_cache[symbol] = (price, time.time())

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
#
# Strategy: try four independent sources in order, return first success.
# Each call has a short timeout so total latency stays bounded.
# Results are cached for 90s so repeated clicks don't hammer APIs.
#
# Sources:
#   1. CoinGecko  — best coverage, but has free-tier rate limits
#   2. Binance    — highly reliable; needs BTC/USDT then USD/ZAR step for non-USD pairs
#   3. CryptoCompare — independent feed, good uptime
#   4. Coinbase   — only BTC/ZAR, ETH/ZAR; narrower but another fallback
#
# The USD→ZAR conversion for Binance uses a live rate from exchangerate-api.
# If that also fails we fall through to the manual-entry UI.

COIN_ID_MAP = {
    'BTC':  'bitcoin',        'ETH':  'ethereum',   'USDT': 'tether',
    'BNB':  'binancecoin',    'SOL':  'solana',      'XRP':  'ripple',
    'USDC': 'usd-coin',       'ADA':  'cardano',     'DOGE': 'dogecoin',
    'LTC':  'litecoin',       'MATIC':'matic-network','DOT': 'polkadot',
    'TRX':  'tron',
}

# Binance trading pairs that are quoted directly in USDT
BINANCE_USDT_PAIRS = {
    'BTC','ETH','BNB','SOL','XRP','ADA','DOGE','LTC','MATIC','DOT','TRX',
}

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (InvestZA price-check)',
    'Accept':     'application/json',
}


def _http_get(url: str, timeout: int = 6) -> dict | None:
    """Fetch a URL, return parsed JSON dict or None on any error."""
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status != 200:
                return None
            return json.loads(r.read().decode('utf-8'))
    except Exception:
        return None


def _source_coingecko(symbol: str) -> Decimal | None:
    """CoinGecko /simple/price — returns ZAR directly."""
    coin_id = COIN_ID_MAP.get(symbol.upper())
    if not coin_id:
        return None
    data = _http_get(
        f"https://api.coingecko.com/api/v3/simple/price"
        f"?ids={coin_id}&vs_currencies=zar&precision=2",
        timeout=7,
    )
    if not data:
        return None
    price = data.get(coin_id, {}).get('zar')
    return Decimal(str(price)) if price else None


def _get_usd_zar() -> Decimal | None:
    """Fetch live USD→ZAR rate from exchangerate-api (free, no key required)."""
    # Try two providers
    for url in [
        'https://api.exchangerate-api.com/v4/latest/USD',
        'https://open.er-api.com/v6/latest/USD',
    ]:
        data = _http_get(url, timeout=5)
        if data:
            rate = (data.get('rates') or data.get('conversion_rates', {})).get('ZAR')
            if rate:
                return Decimal(str(rate))
    return None


def _source_binance(symbol: str) -> Decimal | None:
    """
    Binance ticker — price in USDT, then convert USDT→ZAR.
    USDT itself is ≈ 1 USD, so we multiply by the USD/ZAR rate.
    """
    sym = symbol.upper()
    if sym not in BINANCE_USDT_PAIRS:
        return None

    data = _http_get(
        f"https://api.binance.com/api/v3/ticker/price?symbol={sym}USDT",
        timeout=6,
    )
    if not data or 'price' not in data:
        return None

    usd_price = Decimal(str(data['price']))
    usd_zar   = _get_usd_zar()
    if not usd_zar:
        return None

    return (usd_price * usd_zar).quantize(Decimal('0.01'))


def _source_cryptocompare(symbol: str) -> Decimal | None:
    """CryptoCompare min-api — returns ZAR directly for most major coins."""
    data = _http_get(
        f"https://min-api.cryptocompare.com/data/price"
        f"?fsym={symbol.upper()}&tsyms=ZAR",
        timeout=6,
    )
    if not data:
        return None
    price = data.get('ZAR')
    return Decimal(str(price)) if price else None


def _source_coinbase(symbol: str) -> Decimal | None:
    """Coinbase public prices — only supports a subset of pairs against ZAR."""
    data = _http_get(
        f"https://api.coinbase.com/v2/prices/{symbol.upper()}-ZAR/spot",
        timeout=6,
    )
    if not data:
        return None
    amount = (data.get('data') or {}).get('amount')
    return Decimal(str(amount)) if amount else None


def _fetch_zar_price(symbol: str) -> Decimal | None:
    """
    Try four price sources in order; return first valid result.
    Uses in-memory cache to avoid hammering APIs on every page interaction.
    """
    symbol = symbol.upper()

    # 1. Serve from cache if fresh
    cached = _cache_get(symbol)
    if cached is not None:
        return cached

    # 2. Try each source; first non-None wins
    for source_fn in (
        _source_coingecko,
        _source_binance,
        _source_cryptocompare,
        _source_coinbase,
    ):
        try:
            price = source_fn(symbol)
            if price and price > 0:
                _cache_set(symbol, price)
                return price
        except Exception:
            continue

    return None


@require_GET
@login_required
def crypto_price_api(request):
    """
    AJAX endpoint — returns live ZAR price for a given symbol.
    Tries up to 2 attempts with a short delay between them so that
    a transient API blip doesn't immediately show 'Price unavailable'.
    """
    symbol = request.GET.get('symbol', '').strip().upper()
    if not symbol:
        return JsonResponse({'error': 'No symbol provided'}, status=400)
    try:
        currency = CryptoCurrency.objects.get(symbol__iexact=symbol, is_active=True)
    except CryptoCurrency.DoesNotExist:
        return JsonResponse({'error': 'Currency not found'}, status=404)

    price = _fetch_zar_price(symbol)

    # One retry after a brief pause if all sources failed on first pass
    if price is None:
        time.sleep(1.2)
        price = _fetch_zar_price(symbol)

    if price is None:
        return JsonResponse({
            'error':   'Price unavailable',
            'symbol':  symbol,
            # Signal to front-end that it should show manual fallback
            'manual':  True,
        })

    return JsonResponse({
        'symbol':      symbol,
        'name':        currency.name,
        'price_zar':   float(price),
        'network':     currency.network,
        'min_deposit': float(currency.minimum_deposit),
        'cached':      _cache_get(symbol) is not None,
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
