from django.urls import path
from . import views

urlpatterns = [
    # Customers
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.customer_add, name='customer_add'),
    path('customers/remove/', views.customer_remove, name='customer_remove'),
    path('customer-record/<int:id>/', views.customer_record, name='customer_record'),
    path("orders/payment/<int:id>/", views.update_payment, name="update_payment"),
    
    
    


    # Employees
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/add/', views.employee_add, name='employee_add'),
    path('employees/<int:employee_id>/', views.employee_detail, name='employee_detail'),
    path('employees/<int:employee_id>/delete/', views.employee_delete, name='employee_delete'),
    path('employees/<int:employee_id>/end/', views.end_job, name='end_job'),
    path('employees/<int:employee_id>/calculate/', views.calculate_salary, name='calculate_salary'),
    
]