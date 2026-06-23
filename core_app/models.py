from django.db import models
from people_app.models import Customer


STATUS_CHOICES = [
    ("Pending", "Pending"),
    ("Completed", "Completed"),
    ("Cancelled", "Cancelled"),
    ]

# 🔹 Category
class Category(models.Model):
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to='categories/', null=True, blank=True)
    status = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# 🔹 Dealer (Supplier)
class Dealer(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    address = models.TextField()

    def __str__(self):
        return self.name


# 🔹 Food Item (Inventory)
class FoodItem(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2, blank=True)

    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    dealer = models.ForeignKey(Dealer, on_delete=models.SET_NULL, null=True, blank=True)

    image = models.ImageField(upload_to="food_images/", null=True, blank=True)

    quantity = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    total_sold = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.name} (Stock: {self.quantity})"


# 🔹 Stock Transaction (IN / OUT)
class StockTransaction(models.Model):
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name="stock_transactions")
    quantity = models.IntegerField()  # +ve = add, -ve = reduce
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.food_item.name} | {self.quantity}"


# 🔹 Order
class Order(models.Model):

    PAYMENT_CHOICES = [
        ("Pending", "Pending"),
        ("Cleared", "Cleared"),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Pending"
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE
    )

    order_date = models.DateTimeField(auto_now_add=True)

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_CHOICES,
        default="Pending"
    )

    paid_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    @property
    def total_price(self):
        return sum(
            item.food_item.price * item.quantity
            for item in self.items.all()
      )
    @property
    def remaining_amount(self):
        return self.total_price - self.paid_amount


# 🔹 Order Items
class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} x {self.food_item.name}"
    

class Payment(models.Model):

    order = models.ForeignKey(
        Order,
        related_name="payments",
        on_delete=models.CASCADE
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    note = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment Rs {self.amount} - Order #{self.order.id}"

# Create your models here.
