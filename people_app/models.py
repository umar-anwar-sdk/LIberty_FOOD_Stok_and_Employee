from django.db import models
from django.conf import settings
from django.utils import timezone# Create your models here.
from django.conf import settings


# 🔹 Customer Model
class Customer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, unique=True)
    name = models.CharField(max_length=100)
    # The profile email mirrors the linked login email and is required/unique.
    email = models.EmailField(unique=True)
    address = models.TextField()
    phone = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return self.name


class AuditLog(models.Model):
    """Immutable audit record for destructive administration actions."""
    action = models.CharField(max_length=40)
    object_type = models.CharField(max_length=80)
    object_id = models.PositiveBigIntegerField()
    reason = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="audit_events")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


# 🔹 Employee Model
class Employee(models.Model):
    # Required to establish a stable ownership boundary for employee data.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        unique=True,
        related_name="employee_profile",
    )
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    position = models.CharField(max_length=100)
    join_date = models.DateField()
    is_active = models.BooleanField(default=True)
    base_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


# 🔹 Daily Cash Record
class EmployeeDailyCash(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="daily_cash")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee} - {self.amount} on {self.date}"


# 🔹 Monthly Salary
class EmployeeSalary(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="salaries")
    month = models.DateField(default=timezone.now)
    total_salary = models.DecimalField(max_digits=10, decimal_places=2)
    remaining_salary = models.DecimalField(max_digits=10, decimal_places=2)
    advance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.employee} - {self.month.strftime('%B %Y')}"


# 🔹 Salary Transactions
class EmployeeTransaction(models.Model):
    TRANSACTION_TYPES = (
        ("taken", "Cash Taken"),
        ("deposit", "Cash Deposit"),
    )

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="transactions")
    salary_record = models.ForeignKey(EmployeeSalary, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee} - {self.transaction_type} {self.amount}"
