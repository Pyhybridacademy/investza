"""
investments/forms.py
"""
from django import forms
from .models import Investment, InvestmentPlan
from decimal import Decimal


class CreateInvestmentForm(forms.ModelForm):
    plan = forms.ModelChoiceField(
        queryset=InvestmentPlan.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_plan'})
    )
    amount_invested = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter amount in ZAR',
            'step': '0.01',
            'min': '500',
        })
    )

    class Meta:
        model = Investment
        fields = ['plan', 'amount_invested']

    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_amount_invested(self):
        amount = self.cleaned_data.get('amount_invested')
        plan = self.cleaned_data.get('plan')

        if not amount or amount <= 0:
            raise forms.ValidationError("Please enter a valid amount.")

        if plan:
            if amount < plan.minimum_amount:
                raise forms.ValidationError(
                    f"Minimum investment for this plan is R{plan.minimum_amount:,.2f}"
                )
            if amount > plan.maximum_amount:
                raise forms.ValidationError(
                    f"Maximum investment for this plan is R{plan.maximum_amount:,.2f}"
                )

        if self.user:
            wallet = self.user.get_wallet()
            if wallet.available_balance < amount:
                raise forms.ValidationError(
                    f"Insufficient balance. Your available balance is R{wallet.available_balance:,.2f}"
                )

        return amount
