from django.contrib import admin
from .models import (
    Category,
    Dealer,
    FoodItem,
    StockTransaction,
    Order,
    OrderItem,
)

@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "dealer", "quantity", "price")
    fieldsets = (
        (None, {"fields": ("name", "description", "price", "category", "dealer", "image")} ),
        ("Packaging", {"fields": ("default_unit", "custom_unit_name", "pieces_per_pack", "pieces_per_box", "pieces_per_carton")}),
        ("Inventory", {"fields": ("quantity",)}),
    )

admin.site.register(Category)
admin.site.register(Dealer)
admin.site.register(StockTransaction)
admin.site.register(Order)
admin.site.register(OrderItem)