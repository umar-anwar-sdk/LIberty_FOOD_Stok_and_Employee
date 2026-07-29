from django.shortcuts import render, get_object_or_404, redirect, HttpResponse
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.db import transaction
from django.contrib import messages
from decimal import Decimal
from datetime import datetime
from uuid import uuid4
from django.utils.timezone import now
from core_app.models import Order
import calendar
from django.db.models import Sum
from .models import Employee, Customer
from .forms import CustomerAccountForm, EmployeeAccountForm, update_account_user
from .models import Employee, Customer, EmployeeSalary, EmployeeTransaction
from django.utils.dateparse import parse_date
from django.conf import settings
from accounts.models import CustomUser
from .models import Employee, EmployeeTransaction
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from accounts.decoraters import (
    admin_required,
    is_admin,
)




@admin_required
def customer_list(request):
    customers = Customer.objects.all()
    return render(request, "customer_list.html", {"customers": customers})

@admin_required
def customer_add(request):
    form = CustomerAccountForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            with transaction.atomic():
                user = get_user_model().objects.create_user(
                    username=f"customer-{uuid4().hex}",
                    first_name=form.cleaned_data["name"],
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password"],
                    role="customer",
                )
                Customer.objects.create(
                    user=user,
                    name=form.cleaned_data["name"],
                    email=user.email,
                    address=form.cleaned_data["address"],
                    phone=form.cleaned_data["phone"],
                )
            messages.success(request, "Customer account created successfully.")
            return redirect("customer_list")

    return render(request, "customer_form.html", {"form": form})


@admin_required
def customer_update(request, customer_id):
    """Update a customer and its login account; a blank password keeps it."""
    customer = get_object_or_404(Customer, pk=customer_id)
    form = CustomerAccountForm(
        request.POST or None,
        account_user=customer.user,
        initial={
            "name": customer.name,
            "phone": customer.phone,
            "address": customer.address,
        },
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            if customer.user:
                update_account_user(
                    customer.user,
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password"],
                    first_name=form.cleaned_data["name"],
                )
            else:
                customer.user = get_user_model().objects.create_user(
                    username=f"customer-{uuid4().hex}",
                    first_name=form.cleaned_data["name"],
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password"],
                    role="customer",
                )
            customer.name = form.cleaned_data["name"]
            customer.email = form.cleaned_data["email"]
            customer.phone = form.cleaned_data["phone"]
            customer.address = form.cleaned_data["address"]
            customer.save()
        messages.success(request, "Customer account updated successfully.")
        return redirect("customer_list")
    return render(request, "customer_form.html", {"form": form, "is_update": True})

@admin_required
def customer_remove(request):
    if request.method == "POST":
        customer_id = request.POST.get("customer_id")
        customer = get_object_or_404(Customer, id=customer_id)
        customer.delete()
        return redirect("customer_list")


# ---------------- EMPLOYEES ---------------- #
@admin_required
def employee_add(request):
    form = EmployeeAccountForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            with transaction.atomic():
                data = form.cleaned_data
                User = get_user_model()
                user = User.objects.create_user(
                    username=f"employee-{uuid4().hex}",
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    email=data["email"],
                    password=data["password"],
                    role="employee",
                )
                Employee.objects.create(
                    user=user,
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    position=data["position"],
                    base_salary=data["salary"],
                    join_date=data["join_date"],
                )

            messages.success(request, "Employee account created successfully.")
            return redirect("employee_list")

    return render(request, "employee_form.html", {"form": form})


@admin_required
def employee_update(request, employee_id):
    """Update an employee and its login account; a blank password keeps it."""
    employee = get_object_or_404(Employee, pk=employee_id)
    form = EmployeeAccountForm(
        request.POST or None,
        account_user=employee.user,
        initial={
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "position": employee.position,
            "join_date": employee.join_date,
            "salary": employee.base_salary,
        },
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            if employee.user:
                update_account_user(
                    employee.user,
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password"],
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"],
                )
            else:
                employee.user = get_user_model().objects.create_user(
                    username=f"employee-{uuid4().hex}",
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"],
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password"],
                    role="employee",
                )
            employee.first_name = form.cleaned_data["first_name"]
            employee.last_name = form.cleaned_data["last_name"]
            employee.position = form.cleaned_data["position"]
            employee.join_date = form.cleaned_data["join_date"]
            employee.base_salary = form.cleaned_data["salary"]
            employee.save()
        messages.success(request, "Employee account updated successfully.")
        return redirect("employee_list")
    return render(request, "employee_form.html", {"form": form, "is_update": True})

@admin_required
def employee_list(request):
    employees = Employee.objects.all()
    return render(request, "employee_list.html", {"employees": employees})

@admin_required
def employee_delete(request, employee_id):
    if request.method == "POST":
        employee = get_object_or_404(Employee, id=employee_id)
        user = employee.user
        employee.delete()
        # The employee identity must not remain usable after deletion.
        if user:
            user.delete()
        messages.success(request, f"{employee.first_name} {employee.last_name} has been deleted.")
    return redirect('employee_list')
@login_required
def employee_detail(request, employee_id):
    # An employee can only ever address their own profile.  Admin can manage all.
    if is_admin(request.user):
        employee = get_object_or_404(Employee, id=employee_id)
        can_manage_salary = True
    elif request.user.role == "employee":
        employee = get_object_or_404(Employee, id=employee_id, user=request.user)
        can_manage_salary = False
        if request.method != "GET":
            raise PermissionDenied("Employees cannot modify salary or payroll information.")
    else:
        raise PermissionDenied("You do not have permission to access employee salary data.")

    today = now().date()
    month_start = today.replace(day=1)
    total_days_in_month = calendar.monthrange(today.year, today.month)[1]

    join_date = employee.join_date
    if hasattr(join_date, "date"):
        join_date = join_date.date()

    # ---------------- SALARY CALCULATION ----------------
    monthly_salary = employee.base_salary

    # If employee joined in current month
    if join_date and join_date >= month_start:

        per_day_salary = employee.base_salary / Decimal(total_days_in_month)

        remaining_days = (total_days_in_month - join_date.day) + 1

        if remaining_days < 0:
            remaining_days = 0

        monthly_salary = per_day_salary * Decimal(remaining_days)

    # ---------------- SALARY RECORD ----------------
    if can_manage_salary:
        salary_record, _ = EmployeeSalary.objects.get_or_create(
            employee=employee, month=month_start,
            defaults={"total_salary": monthly_salary, "remaining_salary": monthly_salary,
                      "advance_amount": Decimal("0")},
        )
        salary_record.total_salary = monthly_salary
        if not salary_record.transactions.exists():
            salary_record.remaining_salary = monthly_salary
        salary_record.save()
    else:
        # Viewing must not create or alter a payroll record.  When an admin has
        # not generated this month's record yet, render an in-memory estimate
        # rather than denying the employee access to their own salary page.
        salary_record = EmployeeSalary.objects.filter(employee=employee, month=month_start).first()
        if salary_record is None:
            salary_record = EmployeeSalary(
                employee=employee,
                month=month_start,
                total_salary=monthly_salary,
                remaining_salary=monthly_salary,
                advance_amount=Decimal("0"),
            )

    # ---------------- TRANSACTIONS ----------------
    if can_manage_salary and request.method == "POST" and "action" in request.POST:
        action = request.POST.get("action")

        try:
            amount = Decimal(request.POST.get("amount", "0"))
        except:
            amount = Decimal("0")

        reason = request.POST.get("reason", "")

        if amount <= 0:
            messages.error(request, "Invalid amount")
            return redirect("employee_detail", employee_id=employee.id)

        # CASH TAKEN
        if action == "taken":
            if salary_record.remaining_salary >= amount:
                salary_record.remaining_salary -= amount
            else:
                extra = amount - salary_record.remaining_salary
                salary_record.remaining_salary = Decimal("0")
                salary_record.advance_amount += extra

            EmployeeTransaction.objects.create(
                employee=employee,
                salary_record=salary_record,
                transaction_type="taken",
                amount=amount,
                reason=reason,
            )

        # CASH DEPOSIT
        elif action == "deposit":
            if salary_record.advance_amount > 0:
                if amount <= salary_record.advance_amount:
                    salary_record.advance_amount -= amount
                else:
                    extra = amount - salary_record.advance_amount
                    salary_record.advance_amount = Decimal("0")
                    salary_record.remaining_salary += extra
            else:
                salary_record.remaining_salary += amount

            EmployeeTransaction.objects.create(
                employee=employee,
                salary_record=salary_record,
                transaction_type="deposit",
                amount=amount,
                reason=reason,
            )

        salary_record.save()
        return redirect("employee_detail", employee_id=employee.id)

    # ---------------- DATA ----------------
    if salary_record.pk:
        transactions = salary_record.transactions.all().order_by("-date")
        total_deposit = EmployeeTransaction.objects.filter(
            salary_record=salary_record,
            transaction_type="deposit",
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    else:
        transactions = EmployeeTransaction.objects.none()
        total_deposit = Decimal("0")

    summary = {
        "total_salary": salary_record.total_salary,
        "worked_days_salary": monthly_salary,
        "advance": salary_record.advance_amount,
        "deposit": total_deposit,
        "remaining": salary_record.remaining_salary,
    }

    return render(request, "employee_detail.html", {
        "employee": employee,
        "salary_record": salary_record,
        "transactions": transactions,
        "summary": summary,
    })

@admin_required
def end_job(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    employee.is_active = False
    employee.save()
    if employee.user:
        # EmailBackend honours is_active, so ended employees cannot log in.
        employee.user.is_active = False
        employee.user.save(update_fields=["is_active"])

    messages.success(request, "Employee job ended successfully")
    return redirect("employee_list")
@admin_required
def calculate_salary(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    transactions = EmployeeTransaction.objects.filter(employee=employee)

    context = {
        "employee": employee,
        "transactions": transactions,
        "calculated_salary": None,
        "advance_used": None,
        "remaining_salary": None,
        "period": None,
    }

    if request.method == "POST":
        from_date = parse_date(request.POST.get("from_date"))
        to_date = parse_date(request.POST.get("to_date"))

        if from_date and to_date:
            # daily salary (fixed 30 days logic same as tumhara system)
            daily_salary = employee.base_salary / Decimal(30)

            days = (to_date - from_date).days + 1
            if days < 0:
                days = 0

            calculated_salary = daily_salary * Decimal(days)

            # advance taken (same pattern as tumhare code)
            advance_used = EmployeeTransaction.objects.filter(
                employee=employee,
                transaction_type="taken",
                date__date__range=[from_date, to_date]
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

            remaining_salary = calculated_salary - advance_used

            context.update({
                "calculated_salary": calculated_salary,
                "advance_used": advance_used,
                "remaining_salary": remaining_salary,
                "period": f"{from_date} to {to_date}",
            })

    return render(request, "calculate_salary.html", context)
@admin_required
def customer_record(request, id):

    customer = Customer.objects.get(id=id)

    orders = Order.objects.filter(
        customer=customer
    ).prefetch_related(
        'items__food_item'
    ).order_by('-order_date')

    return render(
        request,
        'customer_record.html',
        {
            'customer': customer,
            'orders': orders
        }
    )


@admin_required
def update_payment(request, id):

    order = get_object_or_404(Order, id=id)

    if request.method == "POST":

        amount = Decimal(request.POST.get("amount") or "0")

        order.paid_amount = order.paid_amount + amount

        if order.paid_amount >= order.total_price:
            order.payment_status = "Cleared"
        else:
            order.payment_status = "Pending"

        order.save()

        messages.success(request, "Payment updated successfully")

        return redirect(
            "customer_record",
            order.customer.id
        )

    return render(request, "update_payment.html", {
        "order": order
    })

