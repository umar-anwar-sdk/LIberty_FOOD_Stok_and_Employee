from django.urls import path
from . import views

urlpatterns = [
    # Customers
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.customer_add, name='customer_add'),
    path('customers/<int:customer_id>/edit/', views.customer_update, name='customer_update'),
    path('customers/remove/', views.customer_remove, name='customer_remove'),
    path('customer-record/<int:id>/', views.customer_record, name='customer_record'),
    path('customers/<int:customer_id>/ledger/', views.customer_ledger_statement, name='customer_ledger_admin'),
    path('customers/<int:customer_id>/manual-entry/', views.customer_manual_entry, name='customer_manual_entry'),
    path('my-ledger/', views.customer_ledger_statement, name='customer_ledger'),
    path('walking-customers/', views.walking_customer_list, name='walking_customer_list'),
    path('walking-customers/add/', views.walking_customer_add, name='walking_customer_add'),
    path('walking-customers/<int:walking_customer_id>/', views.walking_customer_record, name='walking_customer_record'),
    path("orders/payment/<int:id>/", views.update_payment, name="update_payment"),


    # Employees
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/add/', views.employee_add, name='employee_add'),
    path('employees/<int:employee_id>/edit/', views.employee_update, name='employee_update'),
    path('employees/me/edit/', views.employee_self_update, name='employee_self_update'),
    path('employees/<int:employee_id>/', views.employee_detail, name='employee_detail'),
    path('employees/<int:employee_id>/statement/', views.employee_salary_statement, name='employee_salary_admin'),
    path('my-salary-statement/', views.employee_salary_statement, name='employee_salary_statement'),
    path('my-transactions/', views.my_transactions, name='my_transactions'),
    path('employees/<int:employee_id>/transactions/print/', views.employee_transactions_print, name='employee_transactions_print'),
    path('employees/<int:employee_id>/statement/print/', views.employee_salary_print, name='employee_salary_print'),
    path('employees/<int:employee_id>/delete/', views.employee_delete, name='employee_delete'),
    path('employees/<int:employee_id>/end/', views.end_job, name='end_job'),
    path('employees/<int:employee_id>/calculate/', views.calculate_salary, name='calculate_salary'),
    
]
