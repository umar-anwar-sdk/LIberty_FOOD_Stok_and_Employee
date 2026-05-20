from django.contrib import admin
from .models import (
    Customer,
    Employee,
    EmployeeDailyCash,
    EmployeeSalary,
    EmployeeTransaction,
)

admin.site.register(Customer)
admin.site.register(Employee)
admin.site.register(EmployeeDailyCash)
admin.site.register(EmployeeSalary)
admin.site.register(EmployeeTransaction)