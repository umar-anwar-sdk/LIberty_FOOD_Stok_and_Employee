from django.db import models
from people_app.models import Customer, WalkingCustomer


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

    # Inventory is stored as base pieces (e.g. pieces or bottles)
    quantity = models.PositiveIntegerField(default=0)

    # Packaging configuration (admin-editable)
    UNIT_CHOICES = [
        ("unit", "Piece"),
        ("pack", "Pack"),
        ("box", "Box"),
        ("carton", "Carton"),
        ("bottle", "Bottle"),
    ]
    default_unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default="unit")
    # pieces/bottles per pack/box/carton. Admin can configure these per item.
    pieces_per_pack = models.PositiveIntegerField(default=1)
    pieces_per_box = models.PositiveIntegerField(default=0)
    pieces_per_carton = models.PositiveIntegerField(default=0)
    # Optional custom unit name (e.g., "Bottle", "Spray")
    custom_unit_name = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    total_sold = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.name} (Stock: {self.quantity})"

    def pieces_per(self, unit_type: str) -> int:
        """Return the number of base pieces that a single `unit_type` represents.

        unit_type is one of: 'unit','pack','box','carton'.
        Falls back to sensible defaults.
        """
        if unit_type == "unit":
            return 1
        if unit_type == "pack":
            return max(1, int(self.pieces_per_pack or 1))
        if unit_type == "box":
            # if pieces_per_box not set, try box = packs * pieces_per_pack when possible
            if self.pieces_per_box:
                return int(self.pieces_per_box)
            return int(self.pieces_per_pack or 1)
        if unit_type == "carton":
            if self.pieces_per_carton:
                return int(self.pieces_per_carton)
            return int(self.pieces_per_pack or 1)
        return 1


# 🔹 Stock Transaction (IN / OUT)
class StockTransaction(models.Model):
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name="stock_transactions")
    # The raw unit quantity entered (e.g. 2 packs)
    quantity = models.IntegerField()
    # Unit type recorded for the transaction. Examples: unit, pack, box, carton
    UNIT_CHOICES = [
        ("unit", "Piece"),
        ("pack", "Pack"),
        ("box", "Box"),
        ("carton", "Carton"),
    ]
    unit_type = models.CharField(max_length=20, choices=UNIT_CHOICES, default="unit")
    # How many pieces are in a single unit (pieces per pack/box/carton)
    pieces_per_unit = models.PositiveIntegerField(default=1)
    # Calculated total pieces affected by this transaction (quantity * pieces_per_unit)
    total_pieces = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.food_item.name} | {self.quantity} {self.unit_type} ({self.total_pieces} pcs)"


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

    customer_name = models.CharField(max_length=120, blank=True, default='')
    customer_phone = models.CharField(max_length=20, blank=True, default='')
    customer = models.ForeignKey(
        Customer,
        blank=True,
        null=True,
        related_name="orders",
        on_delete=models.SET_NULL,
    )
    walking_customer = models.ForeignKey(
        WalkingCustomer,
        blank=True,
        null=True,
        related_name="walking_orders",
        on_delete=models.SET_NULL,
    )
    manual_order = models.BooleanField(default=False)
    manual_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    bill_snapshot = models.ImageField(upload_to='manual_orders/', null=True, blank=True)
    notes = models.TextField(blank=True, default='')

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
        if self.manual_order:
            return self.manual_order_amount or 0
        return sum(
            item.line_total
            for item in self.items.all()
        )

    @property
    def remaining_amount(self):
        return self.total_price - self.paid_amount

    @property
    def customer_label(self):
        if self.customer:
            return self.customer.name
        if self.walking_customer:
            return str(self.walking_customer)
        return self.customer_name or "Walk-in"

    @property
    def customer_link_id(self):
        if self.customer:
            return self.customer.id
        if self.walking_customer:
            return self.walking_customer.id
        return None

    @property
    def customer_url_text(self):
        if self.walking_customer:
            return "walking_customer_record"
        if self.customer:
            return "customer_record"
        return None


# 🔹 Order Items
class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    # Keep the price charged at the time of sale; catalogue prices may change.
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    @property
    def line_total(self):
        return (self.unit_price if self.unit_price is not None else self.food_item.price) * self.quantity

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


class CustomerLedgerEntry(models.Model):
    """The customer receivable sub-ledger. Debit increases what is owed."""
    ENTRY_TYPES = (
        ("order", "Order charge"),
        ("payment", "Payment received"),
        ("refund", "Refund"),
        ("adjustment", "Adjustment"),
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="ledger_entries")
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.CASCADE, related_name="ledger_entries")
    payment = models.OneToOneField(Payment, null=True, blank=True, on_delete=models.CASCADE, related_name="ledger_entry")
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES)
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.CharField(max_length=255, blank=True)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("occurred_at", "id")
        indexes = [models.Index(fields=["customer", "occurred_at"])]
        constraints = [
            models.UniqueConstraint(fields=["order", "entry_type"], name="one_order_charge_per_order_type"),
        ]

    @property
    def full_description(self):
        if self.entry_type == "order":
            return f"Order #{self.order.id}"
        return self.description or self.get_entry_type_display()


class WalkingCustomerLedgerEntry(models.Model):
    ENTRY_TYPES = (
        ("order", "Order charge"),
        ("payment", "Payment received"),
        ("refund", "Refund"),
        ("adjustment", "Adjustment"),
    )
    walking_customer = models.ForeignKey(
        WalkingCustomer,
        on_delete=models.CASCADE,
        related_name="ledger_entries",
    )
    order = models.ForeignKey(
        Order,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="walking_ledger_entries",
    )
    payment = models.OneToOneField(
        Payment,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="walking_ledger_entry",
    )
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES)
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.CharField(max_length=255, blank=True)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("occurred_at", "id")
        indexes = [models.Index(fields=["walking_customer", "occurred_at"])]
        constraints = [
            models.UniqueConstraint(fields=["order", "entry_type"], name="one_walking_order_charge_per_order_type"),
        ]

    def __str__(self):
        return f"{self.walking_customer} - {self.get_entry_type_display()}"


class CustomerManualLedgerEntry(models.Model):
    ENTRY_TYPES = (
        ("debit", "Debit"),
        ("credit", "Credit"),
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="manual_ledger_entries",
    )
    order = models.ForeignKey(
        'Order',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='manual_order_entries',
    )
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True)
    entry_date = models.DateField()
    attachment = models.FileField(blank=True, null=True, upload_to="customer_slips/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("entry_date", "id")

    def __str__(self):
        return f"{self.get_entry_type_display()} Rs. {self.amount} - {self.customer}"

# Create your models here.
