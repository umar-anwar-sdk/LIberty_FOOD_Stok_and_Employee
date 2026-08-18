import logging

from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from accounts.decoraters import admin_required
from core_app.models import Customer
from people_app.models import Employee


User = get_user_model()
logger = logging.getLogger(__name__)


def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password")

        # Diagnostic trail: deliberately never log the password or its hash.
        # These messages identify the exact request path and lookup outcomes.
        user_record = User.objects.filter(email__iexact=email).first()
        customer_record = (
            Customer.objects.filter(user=user_record).first() if user_record else None
        )
        employee_record = (
            Employee.objects.filter(user=user_record).first() if user_record else None
        )
        logger.info(
            "auth login: path=%s email=%r user_id=%s role=%s active=%s "
            "customer_id=%s employee_id=%s password_supplied=%s",
            request.path,
            email,
            getattr(user_record, "pk", None),
            getattr(user_record, "role", None),
            getattr(user_record, "is_active", None),
            getattr(customer_record, "pk", None),
            getattr(employee_record, "pk", None),
            bool(password),
        )

        # EmailBackend does the case-insensitive User lookup, check_password(),
        # and is_active validation. Customer/Employee records never gate login.
        user = authenticate(request, email=email, password=password)
        logger.info(
            "auth login result: path=%s email=%r authenticated_user_id=%s role=%s",
            request.path,
            email,
            getattr(user, "pk", None),
            getattr(user, "role", None),
        )

        if user is not None:
            login(request, user)
            request.session.set_expiry(3600)
            logger.info(
                "auth login redirect: user_id=%s role=%s destination=home",
                user.pk,
                user.role,
            )
            return redirect("home")

        messages.error(request, "Invalid credentials")

    return render(request, "login.html")

@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


def signup_view(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        logger.info(
            "auth signup: path=%s email=%r password_supplied=%s confirmation_matches=%s",
            request.path,
            email,
            bool(password),
            password == confirm_password,
        )

        # Validation
        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect("signup")

        # Check existing email
        # Check if already user exists
        existing_user = User.objects.filter(email__iexact=email).first()
        logger.info(
            "auth signup user lookup: email=%r user_id=%s",
            email,
            getattr(existing_user, "pk", None),
        )
        if existing_user:
            messages.error(request, "Email already exists")
            return redirect("signup")


        # This check applies only to customer self-registration, never login.
        customer = Customer.objects.filter(email__iexact=email).first()
        logger.info(
            "auth signup customer lookup: email=%r customer_id=%s; "
            "missing_customer_triggers_registration_error=%s",
            email,
            getattr(customer, "pk", None),
            customer is None,
        )

        if not customer:
            # This is the one and only line that emits the reported message.
            messages.error(request, "This email is not registered as a customer")
            return redirect("signup")

        # Username generate from email
        username = email.split("@")[0]

        # Avoid duplicate usernames
        if User.objects.filter(username=username).exists():
            username = f"{username}{User.objects.count() + 1}"

        # Create user
        user = User.objects.create(
            username=username,
            first_name=customer.name,
            last_name=last_name,
            email=email,
            password=make_password(password),
            role="customer"
)

        customer.user = user
        customer.save()

        messages.success(request, "Account created successfully")
        return redirect("login")

    return render(request, "signup.html")



def dashboard_redirect(request):

    # All roles use the existing root URL; ``home`` chooses its existing
    # role-specific template and context.
    return redirect('home')
    
@login_required
def profile(request):
    return render(request, 'profile.html')


@login_required
def edit_profile(request):
    # Allow users to edit their own profile. Admins may continue to use
    # admin interfaces for broader edits; this endpoint updates only the
    # authenticated user's record and associated customer row when present.
    if request.method == "POST":
        user = request.user
        # Basic personal fields
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name

        email = request.POST.get("email", "").strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            messages.error(request, "Email already exists")
            return redirect("edit_profile")
        user.email = email

        # Phone and profile image
        user.phone = request.POST.get("phone")
        if request.FILES.get("profile_image"):
            user.profile_image = request.FILES["profile_image"]

        # Password: only update when explicitly provided
        new_password = request.POST.get("password", "")
        if new_password:
            user.set_password(new_password)

        user.save()

        # If this user is also a Customer, update the Customer record fields
        if getattr(user, "role", None) == "customer":
            try:
                customer = Customer.objects.get(user=user)
            except Customer.DoesNotExist:
                customer = None
            if customer is not None:
                # Update customer-facing fields when provided
                name = request.POST.get("customer_name")
                if name is not None:
                    customer.name = name
                # Address and phone may be intentionally emptied by the user;
                # presence in POST implies intentional change.
                if "address" in request.POST:
                    customer.address = request.POST.get("address")
                if "phone" in request.POST:
                    customer.phone = request.POST.get("phone")
                customer.email = user.email
                customer.save()

        return redirect("profile")

    # Provide customer record to template when available for pre-filling
    customer = None
    if request.user.role == "customer":
        try:
            customer = Customer.objects.get(user=request.user)
        except Customer.DoesNotExist:
            customer = None
    return render(request, "edit_profile_user.html", {"customer": customer})
