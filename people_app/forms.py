"""Admin-only forms for profiles that also own a Django login account."""

from datetime import date
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from .models import Customer


def update_account_user(user, *, email, password="", first_name="", last_name=""):
    """Apply account changes without ever reading or exposing a password hash."""
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    if password:
        user.set_password(password)
    user.save()
    return user


class AccountEmailMixin:
    """Shared validation for the email used as the authentication identifier."""

    def __init__(self, *args, account_user=None, **kwargs):
        self.account_user = account_user
        super().__init__(*args, **kwargs)
        if account_user:
            self.fields["email"].initial = account_user.email
        # PasswordInput never renders a saved value.  A blank value on update
        # means "leave the existing Django password hash untouched".
        self.fields["password"].required = account_user is None

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        User = get_user_model()
        conflict = User.objects.filter(email__iexact=email)
        if self.account_user:
            conflict = conflict.exclude(pk=self.account_user.pk)
        if conflict.exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class CustomerAccountForm(AccountEmailMixin, forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20, required=False)
    address = forms.CharField(widget=forms.Textarea, required=False)
    password = forms.CharField(widget=forms.PasswordInput(render_value=False))

    def clean_email(self):
        email = super().clean_email()
        conflict = Customer.objects.filter(email__iexact=email)
        if self.account_user:
            conflict = conflict.exclude(user=self.account_user)
        if conflict.exists():
            raise forms.ValidationError("A customer with this email already exists.")
        return email


class EmployeeAccountForm(AccountEmailMixin, forms.Form):
    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    position = forms.CharField(max_length=100)
    join_date = forms.DateField()
    salary = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput(render_value=False))


class ManualCustomerOrderForm(forms.Form):
    order_date = forms.DateField(required=True, initial=date.today)
    bill_amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    paid_amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, initial=0)
    notes = forms.CharField(widget=forms.Textarea, required=False)
    bill_snapshot = forms.ImageField(required=False)

    def clean_paid_amount(self):
        paid = self.cleaned_data.get("paid_amount") or Decimal("0.00")
        bill = self.cleaned_data.get("bill_amount")
        if bill is None:
            return paid
        if paid < 0:
            raise forms.ValidationError("Paid amount cannot be negative.")
        if paid > bill:
            raise forms.ValidationError("Paid amount cannot exceed bill amount.")
        return paid
