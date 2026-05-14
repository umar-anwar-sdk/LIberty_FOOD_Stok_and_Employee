from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone# Create your models here.
from django.conf import settings


# 🔹 Customer Model
class Customer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    address = models.TextField()
    phone = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return self.name


# 🔹 Employee Model
class Employee(models.Model):
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