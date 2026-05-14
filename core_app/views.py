from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Sum, Count
from django.utils.dateparse import parse_date
from decimal import Decimal
import json
import calendar
from .models import Category, Dealer, FoodItem, Order, OrderItem
from people_app.models import Customer, Employee
from django.db.models.functions import ExtractMonth
from django.contrib.auth.decorators import login_required




# ---------------- HOME ---------------- #

@login_required
def home(request):

    # ---------------- STATS ---------------- #
    total_employees = Employee.objects.count()
    total_food_items = FoodItem.objects.count()
    total_stock = FoodItem.objects.aggregate(total=Sum("quantity"))["total"] or 0
    total_orders = Order.objects.count()

    # ---------------- FOOD STOCK CHART ---------------- #
    food_names = list(FoodItem.objects.values_list("name", flat=True))
    food_quantities = list(FoodItem.objects.values_list("quantity", flat=True))

    # ---------------- ORDERS STATUS ---------------- #
    review_labels = ["Completed", "Pending", "Cancelled"]
    review_counts = [
        Order.objects.filter(status="Completed").count(),
        Order.objects.filter(status="Pending").count(),
        Order.objects.filter(status="Cancelled").count(),
    ]

    # ---------------- RECENT ORDERS ---------------- #
    recent_orders = Order.objects.select_related("customer").prefetch_related("items__food_item").order_by("-id")[:5]

    # ---------------- TOP SELLING FOOD ---------------- #
    top_food = (
        OrderItem.objects
        .values("food_item__name")
        .annotate(total=Sum("quantity"))
        .order_by("-total")[:5]
    )

    top_food_labels = [item["food_item__name"] for item in top_food]
    top_food_counts = [item["total"] for item in top_food]

    # ---------------- EMPLOYEE CHART ---------------- #
    employee_data = (
        Employee.objects
        .annotate(month=ExtractMonth("join_date"))
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

    # ---------------- CONTEXT ---------------- #
    return render(request, "home.html", {
        "total_employees": total_employees,
        "total_food_items": total_food_items,
        "total_stock": total_stock,
        "total_orders": total_orders,

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

# def dashboard_view(request):
#     completed_count = Order.objects.filter(status='Completed').count()
#     pending_count = Order.objects.filter(status='Pending').count()
#     cancelled_count = Order.objects.filter(status='Cancelled').count()

#     return render(request, 'dashboard.html', {
#         'review_labels': ["Completed", "Pending", "Cancelled"],
#         'review_counts': [completed_count, pending_count, cancelled_count],
#     })


# ---------------- CATEGORY ---------------- #

def category_list(request):
    return render(request, "category_list.html", {
        "categories": Category.objects.all()
    })


def add_category(request):
    if request.method == "POST":
        Category.objects.create(
            name=request.POST.get("name"),
            image=request.FILES.get("image"),
            status=request.POST.get("status")
        )
        return redirect('category_list')

    return render(request, "add_category.html")


def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        category.name = request.POST.get("name")
        category.save()
        return redirect("category_list")
    return render(request, "category_edit.html", {"category": category})


def category_delete(request, pk):
    get_object_or_404(Category, pk=pk).delete()
    return redirect('category_list')


# ---------------- DEALER ---------------- #

def dealer_list(request):
    return render(request, "dealer_list.html", {
        "dealers": Dealer.objects.all()
    })


def add_dealer(request):
    if request.method == "POST":
        Dealer.objects.create(
            name=request.POST.get("name"),
            phone=request.POST.get("phone"),
            address=request.POST.get("address")
        )
        return redirect("dealer_list")

    return render(request, "add_dealer.html")


def delete_dealer(request, id):
    dealer = get_object_or_404(Dealer, id=id)
    dealer.delete()
    return redirect("dealer_list")


# ---------------- FOOD ---------------- #

def fooditem_list(request):
    return render(request, "fooditem_list.html", {
        "items": FoodItem.objects.all()
    })


def fooditem_detail(request, pk):
    item = get_object_or_404(FoodItem, pk=pk)
    return render(request, "fooditem_detail.html", {"item": item})

def fooditem_add(request):
    if request.method == "POST":
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

        FoodItem.objects.create(
            name=request.POST.get("name"),
            description=request.POST.get("description"),
            price=request.POST.get("price"),
            category=category,
            dealer=dealer,
            image=image   # ✅ safe even if empty
        )

        return redirect("fooditem_list")

    return render(request, "fooditem_form.html", {
        "categories": Category.objects.all(),
        "dealers": Dealer.objects.all()
    })


def fooditem_edit(request, pk):
    item = get_object_or_404(FoodItem, pk=pk)
    if request.method == "POST":
        item.name = request.POST.get("name")
        item.description = request.POST.get("description")
        item.price = request.POST.get("price")
        item.category_id = request.POST.get("category")
        item.dealer_id = request.POST.get("dealer")
        item.save()
        return redirect("fooditem_list")

    return render(request, "fooditem_form.html", {
        "item": item,
        "categories": Category.objects.all(),
        "dealers": Dealer.objects.all()
    })


def fooditem_delete(request, pk):
    item = get_object_or_404(FoodItem, pk=pk)
    item.delete()
    return redirect("fooditem_list")

def add_food_quantity(request):
    if request.method == "POST":
        for fid, qty in zip(request.POST.getlist("food_item"), request.POST.getlist("quantity")):
            food = get_object_or_404(FoodItem, id=fid)
            food.quantity += int(qty)
            food.save()

        return redirect("fooditem_list")

    return render(request, "add_stock.html", {
        "items": FoodItem.objects.all()
    })


# ---------------- ORDERS ---------------- #

def order_list(request):
    return render(request, "order_list.html", {
        "orders": Order.objects.all()
    })


def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    return render(request, "order_detail.html", {
        "order": order,
        "items": OrderItem.objects.filter(order=order)
    })


def create_order(request):
    customers = Customer.objects.all()
    food_items = FoodItem.objects.all()

    if request.method == "POST":
        customer = get_object_or_404(Customer, id=request.POST.get("customer"))
        order = Order.objects.create(customer=customer)

        for fid, qty in zip(request.POST.getlist("food_item"), request.POST.getlist("quantity")):
            food = get_object_or_404(FoodItem, id=fid)
            if food.quantity < int(qty):
                messages.error(request, "Stock issue")
                order.delete()
                return redirect("order_list")

            OrderItem.objects.create(order=order, food_item=food, quantity=int(qty))
            food.quantity -= int(qty)
            food.save()

        return redirect("order_list")

    return render(request, "create_order.html", {
        "customers": customers,
        "food_items": food_items
    })

def order_edit(request, pk):
    order = get_object_or_404(Order, pk=pk)

    if request.method == "POST":
        customer_id = request.POST.get("customer")
        food_item_id = request.POST.get("food_item")
        quantity = int(request.POST.get("quantity", 1))

        order.customer_id = customer_id
        order.save()

        order_item = order.items.first()
        if order_item:
            order_item.food_item_id = food_item_id
            order_item.quantity = quantity
            order_item.save()
        else:
            OrderItem.objects.create(order=order, food_item_id=food_item_id, quantity=quantity)

        return redirect("order_detail", pk=order.pk)

    return render(request, "order_edit.html", {"order": order})

def order_delete(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == "POST":
        order.delete()
        return redirect("order_list")
    return render(request, "order_confirm_delete.html", {"order": order})


# ---------------- SEARCH ---------------- #

def global_search(request):
    q = request.GET.get("q", "")

    return render(request, "search_results.html", {
        "query": q,
        "food": FoodItem.objects.filter(name__icontains=q),
        "customers": Customer.objects.filter(name__icontains=q),
        "employees": Employee.objects.filter(first_name__icontains=q),
        "orders": Order.objects.filter(id__icontains=q),
    })

# ----------------- Custom User -----------------

# @login_required
# def dashboard(request):
#     if request.user.role != "employee":
#         return redirect("login")

#     return render(request, "dashboard.html")


# @login_required
# def customer_home(request):
#     if request.user.role != "customer":
#         return redirect("login")

#     return render(request, "customer_home.html")

