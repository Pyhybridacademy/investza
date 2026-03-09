"""
accounts/forms.py
User registration, login, and profile forms
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from .models import BankAccount, KYCDocument

User = get_user_model()


class UserRegistrationForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-navy-600 focus:border-transparent',
            'placeholder': 'First Name'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-navy-600 focus:border-transparent',
            'placeholder': 'Last Name'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-navy-600 focus:border-transparent',
            'placeholder': 'Email Address'
        })
    )
    phone_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-navy-600 focus:border-transparent',
            'placeholder': '+27 82 000 0000'
        })
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-navy-600 focus:border-transparent',
            'placeholder': 'Create a strong password'
        })
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-navy-600 focus:border-transparent',
            'placeholder': 'Confirm your password'
        })
    )
    referral_code = forms.CharField(
        max_length=8, required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-navy-600 focus:border-transparent',
            'placeholder': 'Referral code (optional)'
        })
    )
    agree_terms = forms.BooleanField(
        required=True,
        error_messages={'required': 'You must agree to the Terms and Conditions.'}
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_referral_code(self):
        code = self.cleaned_data.get('referral_code')
        if code:
            try:
                User.objects.get(referral_code=code)
            except User.DoesNotExist:
                raise forms.ValidationError("Invalid referral code.")
        return code

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email'].split('@')[0] + str(user.pk or '')[:4]
        user.email = self.cleaned_data['email']
        user.phone_number = self.cleaned_data.get('phone_number', '')

        referral_code = self.cleaned_data.get('referral_code')
        if referral_code:
            try:
                referrer = User.objects.get(referral_code=referral_code)
                user.referred_by = referrer
            except User.DoesNotExist:
                pass

        if commit:
            user.save()
            # Create wallet automatically
            from apps.accounts.models import Wallet
            Wallet.objects.get_or_create(user=user)
        return user


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-navy-600 focus:border-transparent',
            'placeholder': 'Email Address',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-navy-600 focus:border-transparent',
            'placeholder': 'Password'
        })
    )


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'date_of_birth', 'id_number', 'profile_photo']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'id_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'SA ID / Passport Number'}),
        }


class BankAccountForm(forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = ['bank_name', 'account_holder', 'account_number', 'account_type', 'branch_code', 'is_primary']
        widgets = {
            'bank_name': forms.Select(attrs={'class': 'form-select'}),
            'account_holder': forms.TextInput(attrs={'class': 'form-input'}),
            'account_number': forms.TextInput(attrs={'class': 'form-input'}),
            'account_type': forms.Select(attrs={'class': 'form-select'}),
            'branch_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 250655'}),
        }


class KYCDocumentForm(forms.ModelForm):
    class Meta:
        model = KYCDocument
        fields = ['document_type', 'document_file']
        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-select'}),
        }
