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




def customer_list(request):
    customers = Customer.objects.all()
    return render(request, "customer_list.html", {"customers": customers})


def customer_add(request):
    if request.method == "POST":
        name = request.POST.get("name")
        address = request.POST.get("address")
        phone = request.POST.get("phone")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if not email:
            email = f"user{phone}@gmail.com"  # temporary unique hack

        if CustomUser.objects.filter(username=email).exists():
            return HttpResponse("User already exists")

        user = CustomUser.objects.create_user(
            username=email,
            email=email,
            first_name=name,
            password=password
        )

        Customer.objects.create(
            user=user,
            name=name,
            address=address,
            phone=phone
        )

        return redirect("customer_list")

    return render(request, "customer_form.html")


def customer_remove(request):
    if request.method == "POST":
        customer_id = request.POST.get("customer_id")
        customer = get_object_or_404(Customer, id=customer_id)
        customer.delete()
        return redirect("customer_list")


# ---------------- EMPLOYEES ---------------- #

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


def employee_list(request):
    employees = Employee.objects.all()
    return render(request, "employee_list.html", {"employees": employees})


def employee_delete(request, employee_id):
    if request.method == "POST":
        employee = get_object_or_404(Employee, id=employee_id)
        employee.delete()
        messages.success(request, f"{employee.first_name} {employee.last_name} has been deleted.")
    return redirect('employee_list')

def employee_detail(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)

    today = now().date()
    month_start = today.replace(day=1)
    total_days_in_month = calendar.monthrange(today.year, today.month)[1]
    monthly_salary = employee.base_salary

    # join_date handle
    join_date = employee.join_date
    if hasattr(join_date, "date"):
        join_date = join_date.date()

    if join_date and join_date >= month_start:
        per_day_salary = employee.base_salary / Decimal(30)
        worked_days = total_days_in_month - join_date.day + 1
        monthly_salary = per_day_salary * Decimal(worked_days)

    # salary record
    salary_record, created = EmployeeSalary.objects.get_or_create(
        employee=employee,
        month=month_start,
        defaults={
            "total_salary": monthly_salary,
            "remaining_salary": monthly_salary,
            "advance_amount": Decimal("0"),
        },
    )

    if request.method == "POST":
        if "action" in request.POST:  # transaction form
            action = request.POST.get("action")
            try:
                amount = Decimal(request.POST.get("amount", "0"))
            except (TypeError, ValueError):
                amount = Decimal("0")
            reason = request.POST.get("reason", "")

            if amount <= 0:
                messages.error(request, "Invalid amount entered.")
                return redirect("employee_detail", employee_id=employee.id)

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

    transactions = salary_record.transactions.all().order_by("-date")

    total_taken = EmployeeTransaction.objects.filter(
        salary_record=salary_record, transaction_type="taken"
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    total_deposit = EmployeeTransaction.objects.filter(
        salary_record=salary_record, transaction_type="deposit"
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


def end_job(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    employee.is_active = False
    employee.save()

    messages.success(request, "Employee job ended successfully")
    return redirect("employee_list")

def calculate_salary(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)

    context = {
        "employee": employee,
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

