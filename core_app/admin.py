from django.contrib import admin
from .models import (
    Category,
    Dealer,
    FoodItem,
    StockTransaction,
    Order,
    OrderItem,
)

admin.site.register(Category)
admin.site.register(Dealer)
admin.site.register(FoodItem)
admin.site.register(StockTransaction)
admin.site.register(Order)
admin.site.register(OrderItem)