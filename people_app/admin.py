from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import (
    Customer,
    Employee,
    EmployeeDailyCash,
    EmployeeSalary,
    EmployeeTransaction,
)

admin.site.register(Customer)
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """Employee records must be linked to an employee-role login account."""
    list_display = ("first_name", "last_name", "position", "user", "is_active")
    list_select_related = ("user",)

    def save_model(self, request, obj, form, change):
        if obj.user and obj.user.role != "employee":
            raise ValidationError("An employee profile must use an Employee user account.")
        super().save_model(request, obj, form, change)
admin.site.register(EmployeeDailyCash)
admin.site.register(EmployeeSalary)
admin.site.register(EmployeeTransaction)
