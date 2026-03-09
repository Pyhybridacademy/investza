"""
deposits/forms.py
"""
from django import forms
from .models import BankDeposit, CryptoDeposit, CryptoCurrency


class BankDepositForm(forms.ModelForm):
    amount = forms.DecimalField(
        max_digits=15, decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter deposit amount (ZAR)',
            'min': '500',
            'step': '0.01',
        })
    )

    class Meta:
        model = BankDeposit
        fields = ['amount']

    def clean_amount(self):
        from django.conf import settings
        amount = self.cleaned_data.get('amount')
        if amount and amount < settings.MIN_DEPOSIT:
            raise forms.ValidationError(f"Minimum deposit is R{settings.MIN_DEPOSIT:,.2f}")
        if amount and amount > settings.MAX_DEPOSIT:
            raise forms.ValidationError(f"Maximum deposit is R{settings.MAX_DEPOSIT:,.2f}")
        return amount


class BankDepositProofForm(forms.ModelForm):
    class Meta:
        model = BankDeposit
        fields = ['proof_of_payment']


class CryptoDepositForm(forms.ModelForm):
    cryptocurrency = forms.ModelChoiceField(
        queryset=CryptoCurrency.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    crypto_amount = forms.DecimalField(
        max_digits=20, decimal_places=8,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '0.00000000',
            'step': '0.00000001',
        })
    )
    zar_amount = forms.DecimalField(
        max_digits=15, decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Equivalent in ZAR',
        })
    )
    exchange_rate_used = forms.DecimalField(
        max_digits=15, decimal_places=2,
        widget=forms.HiddenInput()
    )

    class Meta:
        model = CryptoDeposit
        fields = ['cryptocurrency', 'crypto_amount', 'zar_amount', 'exchange_rate_used']


class CryptoHashForm(forms.ModelForm):
    """Form to submit transaction hash after crypto transfer."""
    class Meta:
        model = CryptoDeposit
        fields = ['transaction_hash', 'from_wallet_address']
        widgets = {
            'transaction_hash': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Transaction hash / TxID'
            }),
            'from_wallet_address': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Your sending wallet address'
            }),
        }


class WithdrawalForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=15, decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Amount to withdraw (ZAR)',
            'min': '200',
            'step': '0.01',
        })
    )
    method = forms.ChoiceField(
        choices=[('BANK', 'Bank Transfer'), ('CRYPTO', 'Cryptocurrency')],
        widget=forms.RadioSelect()
    )
    user_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'rows': 3,
            'placeholder': 'Additional notes (optional)'
        })
    )
