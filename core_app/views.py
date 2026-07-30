from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Sum, Count
from django.db import transaction
from django.utils.dateparse import parse_date
from decimal import Decimal
import json
import calendar
from .models import Category, Dealer, FoodItem, Order, OrderItem
from .ledger import sync_order_ledger, record_payment
from people_app.models import AuditLog
from people_app.models import Customer, Employee
from django.db.models.functions import ExtractMonth
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q

from accounts.decoraters import (
    admin_required,
    is_admin,
)


def delete_with_reason(request, obj, object_type, success_url):
    """Shared server-side enforcement used by every destructive endpoint."""
    reason = (request.POST.get("delete_reason") or "").strip()
    if not reason:
        messages.error(request, "A delete reason is required.")
        return redirect(success_url)
    AuditLog.objects.create(action="delete", object_type=object_type, object_id=obj.pk,
                            reason=reason, actor=request.user)
    obj.delete()
    messages.success(request, f"{object_type} deleted and reason recorded.")
    return redirect(success_url)

# ---------------- HOME ---------------- #

@login_required
def home(request):

    # ---------------- ADMIN & MANAGER ---------------- #

    if is_admin(request.user):

        total_employees = Employee.objects.count()
        total_food_items = FoodItem.objects.count()

        total_stock = (
            FoodItem.objects.aggregate(total=Sum("quantity"))["total"] or 0
        )

        total_orders = Order.objects.count()

        total_customers = Customer.objects.count()
        total_dealers = Dealer.objects.count()
        total_category = Category.objects.count()

        food_names = list(FoodItem.objects.values_list("name", flat=True))
        food_quantities = list(FoodItem.objects.values_list("quantity", flat=True))

        review_labels = ["Completed", "Pending", "Cancelled"]

        review_counts = [
            Order.objects.filter(status="Completed").count(),
            Order.objects.filter(status="Pending").count(),
            Order.objects.filter(status="Cancelled").count(),
        ]

        recent_orders = (
            Order.objects.select_related("customer")
            .prefetch_related("items__food_item")
            .order_by("-id")[:5]
        )
        

        for order in recent_orders:
            order.total_price == sum(
            item.food_item.price * item.quantity
            for item in order.items.all()
    )
        top_food = (
            OrderItem.objects.values("food_item__name")
            .annotate(total=Sum("quantity"))
            .order_by("-total")[:5]
        )

        top_food_labels = [item["food_item__name"] for item in top_food]
        top_food_counts = [item["total"] for item in top_food]

        employee_data = (
            Employee.objects.annotate(month=ExtractMonth("join_date"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

        months = []
        employee_counts = []

        for item in employee_data:
            if item["month"]:
                months.append(calendar.month_name[item["month"]])
                employee_counts.append(item["count"])

        return render(request, "home.html", {
            "total_employees": total_employees,
            "total_food_items": total_food_items,
            "total_stock": total_stock,
            "total_orders": total_orders,
            "customers": total_customers,
            "total_dealers": total_dealers,
            "total_category": total_category,
            "food_names": json.dumps(food_names),
            "food_quantities": json.dumps(food_quantities),
            "review_labels": json.dumps(review_labels),
            "review_counts": json.dumps(review_counts),
            "recent_orders": recent_orders,
            "top_food_labels": json.dumps(top_food_labels),
            "top_food_counts": json.dumps(top_food_counts),
            "months": json.dumps(months),
            "employee_counts": json.dumps(employee_counts),
        })

    # ---------------- EMPLOYEE ---------------- #

    elif request.user.role == 'employee':
        # Employees have no operational/customer access.  Their dashboard is
        # their own profile and read-only salary record.
        employee = get_object_or_404(Employee, user=request.user)
        return redirect("employee_detail", employee_id=employee.id)

    # ---------------- CUSTOMER ---------------- #

    elif request.user.role == 'customer':
        customer = get_object_or_404(Customer, user=request.user)

        customer_orders = Order.objects.filter(
            customer=customer
        ).prefetch_related("items__food_item").order_by("-id")
        return render(
            request,
            "customer.html",
            {
                "customer":customer,
                "customer_orders": customer_orders
            }
        )

    return redirect('login')


# ---------------- CATEGORY ---------------- #

@admin_required
def category_list(request):

    return render(request, "category_list.html", {
        "categories": Category.objects.all()
    })


@admin_required
def add_category(request):

    if request.method == "POST":

        Category.objects.create(
            name=request.POST.get("name"),
            image=request.FILES.get("image"),
            status=request.POST.get("status")
        )

        return redirect('category_list')

    return render(request, "add_category.html")


@admin_required
def fooditem_detail(request, pk):

    item = get_object_or_404(FoodItem, pk=pk)

    total_sold = OrderItem.objects.filter(food_item=item).aggregate(
        total=Sum('quantity')
    )['total'] or 0

    return render(request, "fooditem_detail.html", {
        "item": item,
        "total_sold": total_sold
    })

@admin_required
def category_edit(request, pk):

    category = get_object_or_404(Category, pk=pk)

    if request.method == "POST":
        category.name = request.POST.get("name")
        category.save()
        return redirect("category_list")

    return render(request, "category_edit.html", {"category": category})


@admin_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        return delete_with_reason(request, category, "Category", "category_list")
    return render(request, "delete_reason.html", {"object": category, "cancel_url": "category_list"})


# ---------------- DEALER ---------------- #

@admin_required
def dealer_list(request):

    return render(request, "dealer_list.html", {
        "dealers": Dealer.objects.all()
    })


@admin_required
def add_dealer(request):

    if request.method == "POST":
        Dealer.objects.create(
            name=request.POST.get("name"),
            phone=request.POST.get("phone"),
            address=request.POST.get("address")
        )
        return redirect("dealer_list")

    return render(request, "add_dealer.html")


@admin_required
def delete_dealer(request, id):

    dealer = get_object_or_404(Dealer, id=id)

    if request.method == "POST":
        return delete_with_reason(request, dealer, "Dealer", "dealer_list")

    return render(request, "confirm_delete.html", {"dealer": dealer})
# ---------------- FOOD ---------------- #

@admin_required
def fooditem_list(request):

    return render(request, "fooditem_list.html", {
        "items": FoodItem.objects.all()
    })


@admin_required
def fooditem_add(request):

    if request.method != "POST":
        return render(request, "fooditem_form.html", {
            "categories": Category.objects.all(),
            "dealers": Dealer.objects.all()
        })
    category_id = request.POST.get("category")
    dealer_id = request.POST.get("dealer")

    # category must exist
    if not category_id:
        return render(request, "fooditem_form.html", {
            "error": "Category is required",
            "categories": Category.objects.all(),
            "dealers": Dealer.objects.all()
        })

    category = get_object_or_404(Category, id=category_id)
    dealer = Dealer.objects.filter(id=dealer_id).first() if dealer_id else None

    # image optional
    image = request.FILES.get("image") or None

    fi = FoodItem.objects.create(
        name=request.POST.get("name"),
        description=request.POST.get("description"),
        price=request.POST.get("price"),
        category=category,
        dealer=dealer,
        image=image,
        default_unit=request.POST.get("default_unit") or "unit",
        pieces_per_pack=int(request.POST.get("pieces_per_pack") or 1),
        pieces_per_box=int(request.POST.get("pieces_per_box") or 0),
        pieces_per_carton=int(request.POST.get("pieces_per_carton") or 0),
        custom_unit_name=request.POST.get("custom_unit_name") or None,
    )

    return redirect("fooditem_list")


@admin_required
def fooditem_edit(request, pk):

    item = get_object_or_404(FoodItem, pk=pk)

    if request.method == "POST":
        item.name = request.POST.get("name")
        item.description = request.POST.get("description")
        item.price = request.POST.get("price")
        item.category_id = request.POST.get("category")
        item.dealer_id = request.POST.get("dealer")
        item.default_unit = request.POST.get("default_unit") or item.default_unit
        item.pieces_per_pack = int(request.POST.get("pieces_per_pack") or item.pieces_per_pack)
        item.pieces_per_box = int(request.POST.get("pieces_per_box") or item.pieces_per_box)
        item.pieces_per_carton = int(request.POST.get("pieces_per_carton") or item.pieces_per_carton)
        item.custom_unit_name = request.POST.get("custom_unit_name") or item.custom_unit_name
        item.save()
        return redirect("fooditem_list")

    return render(request, "fooditem_form.html", {
        "item": item,
        "categories": Category.objects.all(),
        "dealers": Dealer.objects.all()
    })


@admin_required
def fooditem_delete(request, pk):

    item = get_object_or_404(FoodItem, pk=pk)
    if request.method == "POST":
        return delete_with_reason(request, item, "Food item", "fooditem_list")
    return render(request, "fooditem_confirm_delete.html", {"item": item})


@admin_required
def add_food_quantity(request):

    if request.method == "POST":
        food_ids = request.POST.getlist("food_item[]") or request.POST.getlist("food_item")
        quantities = request.POST.getlist("quantity[]") or request.POST.getlist("quantity")
        unit_types = request.POST.getlist("unit_type[]") or request.POST.getlist("unit_type")
        pieces_per_units = request.POST.getlist("pieces_per_unit[]") or request.POST.getlist("pieces_per_unit")


        for i, fid in enumerate(food_ids):
            try:
                qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 0
            except (ValueError, TypeError):
                qty = 0

            if qty <= 0:
                continue

            food = get_object_or_404(FoodItem, id=fid)

            unit_type = (unit_types[i] if i < len(unit_types) else "unit") or "unit"

            # pieces per unit: prefer explicit field, otherwise fall back to item's config
            ppu = None
            if i < len(pieces_per_units) and pieces_per_units[i]:
                try:
                    ppu = int(pieces_per_units[i])
                except (ValueError, TypeError):
                    ppu = None
            if not ppu:
                # use item-specific configuration
                try:
                    ppu = int(food.pieces_per(unit_type))
                except Exception:
                    ppu = 1

            total_pieces = qty * ppu

            # Update aggregate stock (stored in pieces)
            food.quantity += int(total_pieces)
            food.save()

            # Record a stock transaction for audit
            try:
                from .models import StockTransaction
                StockTransaction.objects.create(
                    food_item=food,
                    quantity=qty,
                    unit_type=unit_type,
                    pieces_per_unit=ppu,
                    total_pieces=total_pieces,
                )
            except Exception:
                # Do not fail the whole request for an audit write error
                pass

        return redirect("fooditem_list")

    return render(request, "add_stock.html", {
        "items": FoodItem.objects.all()
    })


# ---------------- ORDERS ---------------- #

@admin_required
def order_list(request):

    return render(request, "order_list.html", {
        "orders": Order.objects.all()
    })


@login_required
def order_detail(request, pk):
    # Customer URLs are ownership-scoped, preventing IDOR by changing pk.
    if is_admin(request.user):
        order = get_object_or_404(Order, pk=pk)
    elif request.user.role == "customer":
        # Scope the lookup itself to the authenticated customer's account so
        # an id changed in the URL can never expose another customer's order.
        order = Order.objects.filter(pk=pk, customer__user=request.user).first()
        if order is None:
            raise PermissionDenied("You can only access your own orders.")
    else:
        raise PermissionDenied("You do not have permission to access this order.")

    return render(request, "order_detail.html", {
        "order": order,
        "items": OrderItem.objects.filter(order=order)
    })

@admin_required
def create_order(request):

    customers = Customer.objects.all()
    food_items = FoodItem.objects.all()

    if request.method == "POST":

        customer = get_object_or_404(
            Customer,
            id=request.POST.get("customer")
        )

        try:
            paid_amount = Decimal(request.POST.get("paid_amount") or 0)
        except ArithmeticError:
            messages.error(request, "Enter a valid payment amount.")
            return redirect("order_add")
        if paid_amount < 0:
            messages.error(request, "Payment cannot be negative.")
            return redirect("order_add")
        food_ids = request.POST.getlist("food_item[]")
        quantities = request.POST.getlist("quantity[]")
        # Keep stock, invoice and ledger writes in one database transaction.
        try:
            with transaction.atomic():
                order = Order.objects.create(customer=customer, paid_amount=0, payment_status="Pending")
                total_created = False
                for fid, qty in zip(food_ids, quantities):
                    if not fid or not qty:
                        continue
                    food = get_object_or_404(FoodItem.objects.select_for_update(), id=fid)
                    if not str(qty).isdigit() or int(qty) <= 0 or food.quantity < int(qty):
                        raise ValueError("Stock issue or invalid quantity")
                    OrderItem.objects.create(order=order, food_item=food, quantity=int(qty), unit_price=food.price)
                    food.quantity -= int(qty)
                    food.save(update_fields=["quantity"])
                    total_created = True
                if not total_created:
                    raise ValueError("No items selected")
                total_bill = order.total_price
                if paid_amount > total_bill:
                    raise ValueError("Initial payment cannot exceed the order total.")
                sync_order_ledger(order)
                if paid_amount:
                    record_payment(order, paid_amount, "Initial order payment")
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("order_add")
        messages.success(request, "Order created successfully")
        return redirect("order_list")

    return render(request, "create_order.html", {
        "customers": customers,
        "food_items": food_items
    })
@admin_required
def order_edit(request, pk):

    order = get_object_or_404(Order, pk=pk)

    if request.method == "POST":

        # only update if value exists
        if request.POST.get("customer"):
            order.customer_id = request.POST.get("customer")

        if request.POST.get("status"):
            order.status = request.POST.get("status")

        order.save()

        food_item_id = request.POST.get("food_item")
        quantity = request.POST.get("quantity")

        if food_item_id and quantity:
            quantity = int(quantity)

            order_item = order.items.first()

            if order_item:
                order_item.food_item_id = food_item_id
                order_item.quantity = quantity
                order_item.save()

            else:
                OrderItem.objects.create(
                    order=order,
                    food_item_id=food_item_id,
                    quantity=quantity
                )

        sync_order_ledger(order)
        return redirect("order_detail", pk=order.pk)

    return render(request, "order_edit.html", {"order": order})
@admin_required
def update_order_status(request, pk):
    order = get_object_or_404(Order, pk=pk)

    if request.method == "POST":
        status = request.POST.get("status")

        if status:   # 🔥 VERY IMPORTANT
            order.status = status
            order.save()

    return redirect("order_list")

@admin_required
def order_delete(request, pk):

    order = get_object_or_404(Order, pk=pk)

    if request.method == "POST":
        return delete_with_reason(request, order, "Order", "order_list")

    return render(request, "order_confirm_delete.html", {"order": order})



@admin_required
def dashboard(request):
    recent_orders = Order.objects.prefetch_related('items__food_item').order_by('-order_date')[:10]

    for order in recent_orders:
        order.total_price = sum(
            item.food_item.price * item.quantity
            for item in order.items.all()
        )

    return render(request, 'dashboard.html', {
        'recent_orders': recent_orders
    })


# ---------------- SEARCH ---------------- #
@admin_required
def global_search(request):
    q = request.GET.get("q", "")

    return render(request, "search_results.html", {
        "query": q,
        "food": FoodItem.objects.filter(name__icontains=q),
        "customers": Customer.objects.filter(name__icontains=q),
        "employees": Employee.objects.filter(first_name__icontains=q),
        "orders": Order.objects.filter(id__icontains=q),
})
