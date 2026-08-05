from django.shortcuts import render, get_object_or_404, redirect, HttpResponse
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.db import transaction
from django.contrib import messages
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta
from uuid import uuid4
from django.utils import timezone
from django.utils.timezone import localdate
from core_app.models import Order, CustomerManualLedgerEntry
from core_app.ledger import (
    sync_order_ledger,
    sync_manual_ledger_entry,
    ledger_summary,
    customer_ledger,
    walking_customer_ledger,
    walking_ledger_summary,
)
import calendar
from django.db.models import Sum, Q
from types import SimpleNamespace
from django.core.paginator import Paginator
from .models import (
    Employee,
    Customer,
    EmployeeSalary,
    EmployeeTransaction,
    AuditLog,
    WalkingCustomer,
)
from .forms import CustomerAccountForm, EmployeeAccountForm, update_account_user
from django.utils.dateparse import parse_date
from django.conf import settings
from accounts.models import CustomUser
from django.contrib.auth.decorators import login_required
from accounts.decoraters import (
    admin_required,
    is_admin,
)


MONEY_QUANTUM = Decimal("0.01")


def round_money(value):
    """Round calculated monetary values consistently for display and storage."""
    return Decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def calculate_earned_salary(employee, period_start, period_end, *, as_of=None):
    """Return earned salary for an inclusive period, capped at the current date.

    The calculation starts on the later of the selected period and the
    employee's joining date.  It applies each month's actual number of days,
    so February and 30/31-day months are calculated correctly.
    """
    as_of = as_of or localdate()
    effective_end = min(period_end, as_of)
    effective_start = max(period_start, employee.join_date)

    if effective_start > effective_end:
        return Decimal("0.00"), None, None

    earned_salary = Decimal("0.00")
    cursor = effective_start
    while cursor <= effective_end:
        days_in_month = calendar.monthrange(cursor.year, cursor.month)[1]
        month_end = date(cursor.year, cursor.month, days_in_month)
        chunk_end = min(month_end, effective_end)
        days_worked = (chunk_end - cursor).days + 1

        daily_salary = Decimal(employee.base_salary) / Decimal(days_in_month)
        earned_salary += daily_salary * Decimal(days_worked)
        cursor = month_end + timedelta(days=1)

    return round_money(earned_salary), effective_start, effective_end


def cash_transaction_totals(employee, period_start, period_end):
    """Return ORM totals for cash taken and cash added in the given period.

    ``deposit`` is the existing database value for the UI's Cash Added /
    adjustment action.  Both transaction categories are deductions from the
    earned salary, as required by the current payroll rule.
    """
    if period_start is None or period_end is None:
        return Decimal("0.00"), Decimal("0.00")

    transactions = EmployeeTransaction.objects.filter(
        employee=employee,
        date__date__range=(period_start, period_end),
    )
    cash_taken = transactions.filter(transaction_type="taken").aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")
    cash_added = transactions.filter(transaction_type="deposit").aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")
    return round_money(cash_taken), round_money(cash_added)


def current_month_salary(employee, *, as_of=None):
    """Calculate current earned and remaining salary without relying on stale rows."""
    as_of = as_of or localdate()
    month_start = as_of.replace(day=1)
    earned_salary, period_start, period_end = calculate_earned_salary(
        employee, month_start, as_of, as_of=as_of
    )
    cash_taken, cash_added = cash_transaction_totals(
        employee, period_start, period_end
    )
    days_in_month = calendar.monthrange(as_of.year, as_of.month)[1]
    daily_salary = round_money(Decimal(employee.base_salary) / Decimal(days_in_month))
    days_worked = (
        (period_end - period_start).days + 1
        if period_start is not None
        else 0
    )
    # Both Cash Taken and Cash Added are payroll deductions.
    remaining_salary = round_money(earned_salary - cash_taken - cash_added)
    return {
        "month_start": month_start,
        "daily_salary": daily_salary,
        "days_worked": days_worked,
        "earned_salary": earned_salary,
        "cash_taken": cash_taken,
        "cash_added": cash_added,
        "remaining_salary": remaining_salary,
        "period_start": period_start,
        "period_end": period_end,
    }




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
        reason = (request.POST.get("delete_reason") or "").strip()
        if not reason:
            messages.error(request, "A delete reason is required.")
            return redirect("customer_list")
        AuditLog.objects.create(action="delete", object_type="Customer", object_id=customer.id,
                                reason=reason, actor=request.user)
        customer.delete()
        messages.success(request, "Customer deleted and reason recorded.")
        return redirect("customer_list")


@admin_required
def walking_customer_list(request):
    walking_customers = WalkingCustomer.objects.all()
    return render(request, "walking_customer_list.html", {"walking_customers": walking_customers})


@admin_required
def walking_customer_add(request):
    if request.method == "POST":
        WalkingCustomer.objects.create()
        messages.success(request, "Walking customer token created successfully.")
    return redirect("walking_customer_list")


@admin_required
def walking_customer_record(request, walking_customer_id):
    walking_customer = get_object_or_404(WalkingCustomer, id=walking_customer_id)
    orders = Order.objects.filter(walking_customer=walking_customer).prefetch_related(
        "items__food_item"
    ).order_by("-order_date")
    from core_app.ledger import sync_order_ledger, walking_customer_ledger, walking_ledger_summary
    for order in orders:
        sync_order_ledger(order)
    return render(
        request,
        "walking_customer_record.html",
        {
            "walking_customer": walking_customer,
            "orders": orders,
            "ledger_summary": walking_ledger_summary(walking_customer),
        }
    )


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
        reason = (request.POST.get("delete_reason") or "").strip()
        if not reason:
            messages.error(request, "A delete reason is required.")
            return redirect("employee_detail", employee_id=employee.id)
        name = f"{employee.first_name} {employee.last_name}"
        AuditLog.objects.create(action="delete", object_type="Employee", object_id=employee.id,
                                reason=reason, actor=request.user)
        user = employee.user
        employee.delete()
        # The employee identity must not remain usable after deletion.
        if user:
            user.delete()
        messages.success(request, f"{name} has been deleted and the reason recorded.")
    return redirect('employee_list')
@login_required
def employee_detail(request, employee_id):
    # An employee can only ever address their own profile.  Admin can manage all.
    if is_admin(request.user):
        employee = get_object_or_404(Employee, id=employee_id)
        can_manage_salary = True
    elif request.user.role == "employee":
        # Do not trust the employee id from the URL: it must belong to the
        # authenticated employee before any salary data is read.
        employee = Employee.objects.filter(id=employee_id, user=request.user).first()
        if employee is None:
            raise PermissionDenied("You can only access your own employee record.")
        can_manage_salary = False
        if request.method != "GET":
            raise PermissionDenied("Employees cannot modify salary or payroll information.")
    else:
        raise PermissionDenied("You do not have permission to access employee salary data.")

    salary_data = current_month_salary(employee)

    # The monthly row remains the transaction parent, but admin actions are
    # processed before we overwrite the row's displayed values from the current
    # month calculation, so explicit settlement and transaction posts keep the
    # persisted salary record consistent.
    if can_manage_salary:
        salary_record = EmployeeSalary.objects.filter(
            employee=employee,
            month=salary_data["month_start"],
        ).first()
        if salary_record is None:
            salary_record = EmployeeSalary(
                employee=employee,
                month=salary_data["month_start"],
                total_salary=salary_data["earned_salary"],
                remaining_salary=salary_data["remaining_salary"],
                advance_amount=salary_data["cash_taken"],
            )
        if not (request.method == "POST" and "action" in request.POST):
            salary_record.total_salary = salary_data["earned_salary"]
            salary_record.remaining_salary = salary_data["remaining_salary"]
            salary_record.advance_amount = salary_data["cash_taken"]
            salary_record.save(
                update_fields=["total_salary", "remaining_salary", "advance_amount"]
            )
    else:
        # Employee reads never create or alter payroll rows.
        salary_record = EmployeeSalary.objects.filter(
            employee=employee, month=salary_data["month_start"]
        ).first()
        if salary_record is None:
            salary_record = EmployeeSalary(
                employee=employee,
                month=salary_data["month_start"],
                total_salary=salary_data["earned_salary"],
                remaining_salary=salary_data["remaining_salary"],
                advance_amount=salary_data["cash_taken"],
            )
        else:
            salary_record.total_salary = salary_data["earned_salary"]
            salary_record.remaining_salary = salary_data["remaining_salary"]
            salary_record.advance_amount = salary_data["cash_taken"]

    # ---------------- TRANSACTIONS ----------------
    if can_manage_salary and request.method == "POST" and "action" in request.POST:
        action = request.POST.get("action")

        if action == "clear_month":
            if salary_record is None:
                salary_record = EmployeeSalary.objects.create(
                    employee=employee,
                    month=salary_data["month_start"],
                    total_salary=salary_data["earned_salary"],
                    remaining_salary=salary_data["remaining_salary"],
                    advance_amount=salary_data["cash_taken"],
                )

            salary_record.settled = True
            salary_record.settled_at = timezone.now()
            salary_record.save(update_fields=["total_salary", "remaining_salary", "advance_amount", "settled", "settled_at"])
            messages.success(request, f"Salary for {salary_record.display_month} has been marked as settled.")
            return redirect("employee_detail", employee_id=employee.id)

        try:
            amount = Decimal(request.POST.get("amount", "0"))
        except:
            amount = Decimal("0")

        reason = request.POST.get("reason", "")

        if amount <= 0:
            messages.error(request, "Invalid amount")
            return redirect("employee_detail", employee_id=employee.id)

        if action in {"taken", "deposit"}:
            EmployeeTransaction.objects.create(
                employee=employee,
                salary_record=salary_record,
                transaction_type=action,
                amount=round_money(amount),
                reason=reason,
            )
            salary_record.settled = False
            salary_record.settled_at = None
            salary_record.save(update_fields=["settled", "settled_at"])
        else:
            messages.error(request, "Invalid transaction type")
        return redirect("employee_detail", employee_id=employee.id)

    # ---------------- DATA ----------------
    transactions = EmployeeTransaction.objects.filter(
        employee=employee,
        date__date__range=(salary_data["period_start"], salary_data["period_end"]),
    ).order_by("-date") if salary_data["period_start"] else EmployeeTransaction.objects.none()

    summary = {
        "total_salary": salary_data["earned_salary"],
        "worked_days_salary": salary_data["earned_salary"],
        "advance": salary_data["cash_taken"],
        "deposit": salary_data["cash_added"],
        "remaining": salary_data["remaining_salary"],
    }

    return render(request, "employee_detail.html", {
        "employee": employee,
        "salary_record": salary_record,
        "transactions": transactions,
        "summary": summary,
        # Templates use this capability only for visibility.  The view above
        # remains the source of truth for every write operation.
        "can_manage_salary": can_manage_salary,
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
            calculated_salary, period_start, period_end = calculate_earned_salary(
                employee, from_date, to_date
            )
            advance_used, cash_added = cash_transaction_totals(
                employee, period_start, period_end
            )
            remaining_salary = round_money(
                calculated_salary - advance_used - cash_added
            )

            context.update({
                "calculated_salary": calculated_salary,
                "advance_used": advance_used,
                "remaining_salary": remaining_salary,
                "period": f"{period_start} to {period_end}" if period_start else "No worked days",
            })

    return render(request, "calculate_salary.html", context)
@admin_required
def customer_record(request, id):

    customer = get_object_or_404(Customer, id=id)

    orders = Order.objects.filter(
        customer=customer
    ).prefetch_related(
        'items__food_item'
    ).order_by('-order_date')

    for order in orders:
        sync_order_ledger(order)

    manual_entries = CustomerManualLedgerEntry.objects.filter(customer=customer).order_by('-entry_date', '-id')[:10]
    manual_totals = manual_entries.aggregate(
        debit=Sum('amount', filter=Q(entry_type='debit')),
        credit=Sum('amount', filter=Q(entry_type='credit')),
    )
    manual_debit = manual_totals['debit'] or Decimal('0.00')
    manual_credit = manual_totals['credit'] or Decimal('0.00')
    manual_balance = manual_debit - manual_credit
    order_summary = ledger_summary(customer)
    combined_outstanding = order_summary['outstanding'] + manual_balance

    return render(
        request,
        'customer_record.html',
        {
            'customer': customer,
            'orders': orders,
            'ledger_summary': order_summary,
            'manual_entries': manual_entries,
            'manual_summary': {
                'debit': manual_debit,
                'credit': manual_credit,
                'balance': manual_balance,
            },
            'combined_outstanding': combined_outstanding,
        }
    )


@admin_required
def customer_manual_entry(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)

    if request.method == 'POST':
        entry_type = request.POST.get('entry_type')
        try:
            amount = Decimal(request.POST.get('amount') or '0')
        except (ArithmeticError, ValueError):
            messages.error(request, 'Enter a valid amount.')
            return redirect('customer_record', customer.id)

        if amount <= 0:
            messages.error(request, 'Amount must be greater than zero.')
            return redirect('customer_record', customer.id)

        if entry_type not in {'debit', 'credit'}:
            messages.error(request, 'Select a valid transaction type.')
            return redirect('customer_record', customer.id)

        entry_date = parse_date(request.POST.get('entry_date') or '') or date.today()
        notes = request.POST.get('notes', '').strip()
        attachment = request.FILES.get('attachment')

        manual_entry = CustomerManualLedgerEntry.objects.create(
            customer=customer,
            entry_type=entry_type,
            amount=amount,
            notes=notes,
            entry_date=entry_date,
            attachment=attachment,
        )
        sync_manual_ledger_entry(manual_entry)
        messages.success(request, 'Manual ledger entry recorded successfully.')

    return redirect('customer_record', customer.id)


@admin_required
def update_payment(request, id):

    order = get_object_or_404(Order, id=id)

    if request.method == "POST":

        try:
            from core_app.ledger import record_payment
            record_payment(order, request.POST.get("amount") or "0", request.POST.get("note", ""))
        except (ValueError, ArithmeticError):
            messages.error(request, "Enter a valid payment that does not exceed the outstanding balance.")
            return redirect("update_payment", id=order.id)

        messages.success(request, "Payment updated successfully")

        if order.customer:
            return redirect("customer_record", order.customer.id)
        if order.walking_customer:
            return redirect("walking_customer_record", order.walking_customer.id)
        return redirect("order_list")

    return render(request, "update_payment.html", {
        "order": order
    })


@login_required
def customer_ledger_statement(request, customer_id=None):
    if is_admin(request.user):
        customer = get_object_or_404(Customer, pk=customer_id)
    elif request.user.role == "customer":
        customer = get_object_or_404(Customer, user=request.user)
    else:
        raise PermissionDenied("You do not have permission to access customer ledgers.")
    from core_app.ledger import customer_ledger, ledger_summary
    start, end = parse_date(request.GET.get("start", "")), parse_date(request.GET.get("end", ""))
    if start and end and start > end:
        messages.error(request, "Start date cannot be after end date.")
        start = end = None
    all_entries = customer_ledger(customer)
    filtered_entries = customer_ledger(customer, start=start, end=end, search=request.GET.get("q", ""))
    opening = Decimal("0.00")
    if start:
        for entry in all_entries:
            if entry.occurred_at.date() < start:
                opening += entry.debit - entry.credit
    running = opening
    page = Paginator(filtered_entries, 50).get_page(request.GET.get("page"))
    for entry in page.object_list:
        running += entry.debit - entry.credit
        entry.running_balance = running
    return render(request, "customer_ledger.html", {"customer": customer, "entries": page,
        "summary": ledger_summary(customer), "opening_balance": opening, "start": start, "end": end,
        "query": request.GET.get("q", "")})


@login_required
def employee_salary_statement(request, employee_id=None):
    if is_admin(request.user):
        employee = get_object_or_404(Employee, pk=employee_id)
    elif request.user.role == "employee":
        employee = get_object_or_404(Employee, user=request.user)
    else:
        raise PermissionDenied("You do not have permission to access salary statements.")

    month_value = request.GET.get("month")
    month = parse_date(month_value) if month_value else localdate().replace(day=1)
    if month:
        month_start = month.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)
    else:
        month_start = localdate().replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)

    transactions = EmployeeTransaction.objects.filter(employee=employee, date__date__range=(month_start, month_end)).select_related("salary_record")
    transactions = transactions.order_by("date", "id")
    totals = transactions.aggregate(
        taken=Sum("amount", filter=Q(transaction_type="taken")),
        deposited=Sum("amount", filter=Q(transaction_type="deposit")),
    )
    return render(
        request,
        "salary_statement.html",
        {
            "employee": employee,
            "transactions": transactions,
            "month": month_start,
            "taken": totals["taken"] or 0,
            "deposited": totals["deposited"] or 0,
            "month_label": month_start.strftime("%B %Y"),
        },
    )

