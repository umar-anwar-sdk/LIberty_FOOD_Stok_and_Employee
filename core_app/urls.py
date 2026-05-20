from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.home, name='home'),
    # path('dashboard/', views.dashboard_view, name='dashboard_view'),
    # path('customer/', views.customer_home, name='customer_home'),


    # Search
    path('search/', views.global_search, name='global_search'),

    # Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.add_category, name='add_category'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),

    # Dealers
    path('dealers/', views.dealer_list, name='dealer_list'),
    path('dealers/add/', views.add_dealer, name='add_dealer'),
    path('dealers/<int:id>/delete/', views.delete_dealer, name='delete_dealer'),

    # Food items
    path('foods/', views.fooditem_list, name='fooditem_list'),
    path('foods/add/', views.fooditem_add, name='fooditem_add'),
    path('foods/<int:pk>/', views.fooditem_detail, name='fooditem_detail'),
    path('foods/<int:pk>/edit/', views.fooditem_edit, name='fooditem_edit'),
    path('foods/<int:pk>/delete/', views.fooditem_delete, name='fooditem_delete'),

    # Stock
    path('food_quantity/', views.add_food_quantity, name='food_quantity'),

    # Orders
    path('orders/', views.order_list, name='order_list'),
    path('orders/add/', views.create_order, name='order_add'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('orders/<int:pk>/edit/', views.order_edit, name='order_edit'),
    path('orders/<int:pk>/delete/', views.order_delete, name='order_delete'),
    
]