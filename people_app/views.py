from django.shortcuts import render, get_object_or_404, redirect, HttpResponse
from django.contrib import messages
from decimal import Decimal
from datetime import datetime
from django.utils.timezone import now
from core_app.models import Order
import calendar
from django.db.models import Sum
from .models import Employee, Customer
from .models import Employee, Customer, EmployeeSalary, EmployeeTransaction
from django.utils.dateparse import parse_date
from django.conf import settings
from accounts.models import CustomUser
from .models import Employee, EmployeeTransaction
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from accounts.decoraters import (
    manager_required,
    employee_required,
)




def customer_list(request):
    customers = Customer.objects.all()
    return render(request, "customer_list.html", {"customers": customers})

@employee_required
def customer_add(request):
    if request.method == "POST":
        name = request.POST.get("name")
        address = request.POST.get("address")
        phone = request.POST.get("phone")
        email = request.POST.get("email")
        if not email:
            email = f"user{phone}@gmail.com"  # temporary unique hack

        if CustomUser.objects.filter(email=email).exists():
            return HttpResponse("User already exists")

        Customer.objects.create(
            name=name,
            email=email,
            address=address,
            phone=phone
        )

        return redirect("customer_list")

    return render(request, "customer_form.html")

@employee_required
def customer_remove(request):
    if request.method == "POST":
        customer_id = request.POST.get("customer_id")
        customer = get_object_or_404(Customer, id=customer_id)
        customer.delete()
        return redirect("customer_list")


# ---------------- EMPLOYEES ---------------- #
@manager_required
def employee_add(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        position = request.POST.get("position")
        salary_input = request.POST.get("salary")
        join_date_input = request.POST.get("join_date")  # yyyy-mm-dd format expected

        # validate salary
        try:
            salary = Decimal(salary_input)
        except (TypeError, ValueError):
            salary = Decimal("0")

        # convert join_date string to date object
        join_date = None
        if join_date_input:
            try:
                join_date = datetime.strptime(join_date_input, "%Y-%m-%d").date()
            except ValueError:
                join_date = now().date()

        # create employee
        Employee.objects.create(
            first_name=first_name,
            last_name=last_name,
            position=position,
            base_salary=salary,
            join_date=join_date
        )

        messages.success(request, "Employee added successfully")
        return redirect("employee_list")

    return render(request, "employee_form.html")

@manager_required
def employee_list(request):
    employees = Employee.objects.all()
    return render(request, "employee_list.html", {"employees": employees})

@manager_required
def employee_delete(request, employee_id):
    if request.method == "POST":
        employee = get_object_or_404(Employee, id=employee_id)
        employee.delete()
        messages.success(request, f"{employee.first_name} {employee.last_name} has been deleted.")
    return redirect('employee_list')
@manager_required
def employee_detail(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)

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
    salary_record, created = EmployeeSalary.objects.get_or_create(
        employee=employee,
        month=month_start,
        defaults={
            "total_salary": monthly_salary,
            "remaining_salary": monthly_salary,
            "advance_amount": Decimal("0"),
        },
    )

    # Always sync updated salary
    salary_record.total_salary = monthly_salary

    # Only reset if no transactions exist
    if not salary_record.transactions.exists():
        salary_record.remaining_salary = monthly_salary

    salary_record.save()

    # ---------------- TRANSACTIONS ----------------
    if request.method == "POST" and "action" in request.POST:
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
    transactions = salary_record.transactions.all().order_by("-date")

    total_deposit = EmployeeTransaction.objects.filter(
        salary_record=salary_record,
        transaction_type="deposit"
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

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

@manager_required
def end_job(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    employee.is_active = False
    employee.save()

    messages.success(request, "Employee job ended successfully")
    return redirect("employee_list")
@manager_required
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
@manager_required
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


@manager_required
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

