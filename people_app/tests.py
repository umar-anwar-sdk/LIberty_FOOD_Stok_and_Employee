from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core_app.models import Order, CustomerManualLedgerEntry
from .models import Customer, Employee, EmployeeSalary, EmployeeTransaction
from .views import calculate_earned_salary, current_month_salary


class RoleAccessTests(TestCase):
    """Regression coverage for role checks and object-level ownership."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="password", role="admin"
        )
        self.employee_user = User.objects.create_user(
            username="employee", email="employee@example.com", password="password", role="employee"
        )
        self.other_employee_user = User.objects.create_user(
            username="employee-two", email="employee-two@example.com", password="password", role="employee"
        )
        self.customer_user = User.objects.create_user(
            username="customer", email="customer@example.com", password="password", role="customer"
        )
        self.other_customer_user = User.objects.create_user(
            username="customer-two", email="customer-two@example.com", password="password", role="customer"
        )
        self.employee = Employee.objects.create(
            user=self.employee_user,
            first_name="Employee",
            last_name="One",
            position="Cook",
            join_date=date(2025, 1, 1),
            base_salary="1000.00",
        )
        self.other_employee = Employee.objects.create(
            user=self.other_employee_user,
            first_name="Employee",
            last_name="Two",
            position="Cook",
            join_date=date(2025, 1, 1),
            base_salary="1000.00",
        )
        self.customer = Customer.objects.create(
            user=self.customer_user, name="Customer One", email="customer@example.com", address="A"
        )
        self.other_customer = Customer.objects.create(
            user=self.other_customer_user, name="Customer Two", email="customer-two@example.com", address="B"
        )
        self.order = Order.objects.create(customer=self.customer)
        self.other_order = Order.objects.create(customer=self.other_customer)

    def test_employee_can_only_view_own_read_only_salary_page(self):
        self.client.force_login(self.employee_user)

        response = self.client.get(reverse("employee_detail", args=[self.employee.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "My Profile")
        self.assertContains(response, "My Salary")
        self.assertNotContains(response, ">Customers<")
        self.assertNotContains(response, ">Employees<")
        self.assertNotContains(response, ">Inventory<")
        self.assertNotContains(response, "Add cash transaction")
        self.assertNotContains(response, "End employment")
        self.assertNotContains(response, "Calculate payroll")

        response = self.client.get(reverse("employee_detail", args=[self.other_employee.id]))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(reverse("employee_detail", args=[self.employee.id]), {"action": "taken", "amount": "1"})
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_access_employee_or_admin_management(self):
        self.client.force_login(self.customer_user)

        self.assertEqual(self.client.get(reverse("employee_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("customer_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("employee_detail", args=[self.employee.id])).status_code, 403)

    def test_customer_orders_are_scoped_to_the_logged_in_customer(self):
        self.client.force_login(self.customer_user)

        dashboard = self.client.get(reverse("home"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Dashboard")
        self.assertContains(dashboard, "My Profile")
        self.assertNotContains(dashboard, ">Customers<")
        self.assertNotContains(dashboard, ">Employees<")
        self.assertNotContains(dashboard, ">Inventory<")
        self.assertEqual(self.client.get(reverse("order_detail", args=[self.order.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse("order_detail", args=[self.other_order.id])).status_code, 403)

    def test_current_month_salary_uses_actual_days_and_cash_totals(self):
        self.employee.base_salary = "20000.00"
        self.employee.join_date = date(2026, 7, 1)
        self.employee.save(update_fields=["base_salary", "join_date"])
        salary_record = EmployeeSalary.objects.create(
            employee=self.employee,
            month=date(2026, 7, 1),
            total_salary="0.00",
            remaining_salary="0.00",
        )
        taken = EmployeeTransaction.objects.create(
            employee=self.employee,
            salary_record=salary_record,
            transaction_type="taken",
            amount="3000.00",
        )
        added = EmployeeTransaction.objects.create(
            employee=self.employee,
            salary_record=salary_record,
            transaction_type="deposit",
            amount="1000.00",
        )
        future = EmployeeTransaction.objects.create(
            employee=self.employee,
            salary_record=salary_record,
            transaction_type="taken",
            amount="500.00",
        )
        transaction_date = timezone.make_aware(datetime(2026, 7, 29, 12, 0))
        EmployeeTransaction.objects.filter(pk__in=[taken.pk, added.pk]).update(date=transaction_date)
        EmployeeTransaction.objects.filter(pk=future.pk).update(
            date=timezone.make_aware(datetime(2026, 7, 30, 12, 0))
        )

        result = current_month_salary(self.employee, as_of=date(2026, 7, 29))

        # July 2026 has 31 days: 20,000 / 31 * 29 = 18,709.68.
        self.assertEqual(result["earned_salary"], Decimal("18709.68"))
        self.assertEqual(result["cash_taken"], Decimal("3000.00"))
        self.assertEqual(result["cash_added"], Decimal("1000.00"))
        self.assertEqual(result["daily_salary"], Decimal("645.16"))
        self.assertEqual(result["days_worked"], 29)
        self.assertEqual(result["remaining_salary"], Decimal("14709.68"))

    def test_joining_day_is_the_first_paid_day_and_future_joining_earns_zero(self):
        self.employee.base_salary = "20000.00"
        self.employee.join_date = date(2026, 7, 15)

        earned, start, end = calculate_earned_salary(
            self.employee, date(2026, 7, 1), date(2026, 7, 29), as_of=date(2026, 7, 29)
        )
        self.assertEqual(start, date(2026, 7, 15))
        self.assertEqual(end, date(2026, 7, 29))
        self.assertEqual(earned, Decimal("9677.42"))  # 15 inclusive paid days

        self.employee.join_date = date(2026, 7, 29)
        earned, start, end = calculate_earned_salary(
            self.employee, date(2026, 7, 1), date(2026, 7, 29), as_of=date(2026, 7, 29)
        )
        self.assertEqual(earned, Decimal("645.16"))
        self.assertEqual(start, end)

        self.employee.join_date = date(2026, 7, 30)
        earned, start, end = calculate_earned_salary(
            self.employee, date(2026, 7, 1), date(2026, 7, 29), as_of=date(2026, 7, 29)
        )
        self.assertEqual(earned, Decimal("0.00"))
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_manual_ledger_entry_is_recorded_in_customer_ledger(self):
        from core_app.ledger import sync_manual_ledger_entry
        from core_app.models import CustomerLedgerEntry

        entry = CustomerManualLedgerEntry.objects.create(
            customer=self.customer,
            entry_type="debit",
            amount="1200.00",
            notes="Manual ledger from supplier",
            entry_date=date(2026, 8, 2),
        )

        sync_manual_ledger_entry(entry)

        self.assertTrue(CustomerLedgerEntry.objects.filter(
            customer=self.customer,
            description__icontains="Manual Ledger Entry",
            debit=Decimal("1200.00"),
        ).exists())

    def test_clear_month_sets_salary_as_settled(self):
        self.client.force_login(self.admin)
        self.employee.base_salary = "30000.00"
        self.employee.save(update_fields=["base_salary"])
        EmployeeTransaction.objects.create(
            employee=self.employee,
            salary_record=EmployeeSalary.objects.create(
                employee=self.employee,
                month=date(2026, 8, 1),
                total_salary="30000.00",
                remaining_salary="20000.00",
                advance_amount="0.00",
            ),
            transaction_type="taken",
            amount="10000.00",
            reason="Cash taken",
            date=timezone.make_aware(datetime(2026, 8, 10, 10, 0)),
        )

        response = self.client.post(reverse("employee_detail", args=[self.employee.id]), {"action": "clear_month"})
        self.assertEqual(response.status_code, 302)
        record = EmployeeSalary.objects.get(employee=self.employee, month=date(2026, 8, 1))
        self.assertTrue(record.settled)
        self.assertEqual(record.remaining_salary, Decimal("20000.00"))

    def test_customer_record_page_handles_manual_ledger_entries(self):
        self.client.force_login(self.admin)
        CustomerManualLedgerEntry.objects.create(
            customer=self.customer,
            entry_type="credit",
            amount="250.00",
            notes="Manual ledger note",
            entry_date=date(2026, 8, 3),
        )

        response = self.client.get(reverse("customer_record", args=[self.customer.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Manual Ledger Entry")
        self.assertContains(response, "Manual ledger note")

    def test_manual_ledger_entries_are_shown_in_account_statement(self):
        self.client.force_login(self.admin)
        CustomerManualLedgerEntry.objects.create(
            customer=self.customer,
            entry_type="debit",
            amount="250.00",
            notes="Supplier invoice",
            entry_date=date(2026, 8, 3),
        )

        response = self.client.get(reverse("customer_ledger_admin", args=[self.customer.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Manual Ledger Entry")
        self.assertContains(response, "Supplier invoice")
