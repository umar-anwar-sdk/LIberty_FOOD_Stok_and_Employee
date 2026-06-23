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
from django.db.models import Q

from accounts.decoraters import (
    manager_required,
    employee_required,
)

# ---------------- HOME ---------------- #

@login_required
def home(request):

    # ---------------- ADMIN & MANAGER ---------------- #

    if request.user.role in ['admin', 'manager']:

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

        recent_orders = Order.objects.order_by("-id")[:5]

        return render(
            request,
            "employee.html",
            {
                "recent_orders": recent_orders
            }
        )

    # ---------------- CUSTOMER ---------------- #

    elif request.user.role == 'customer':
        print("CUSTOMER BLOCK RUNNING")

        customer = Customer.objects.get(
            user=request.user
        )

        customer_orders = Order.objects.filter(
            customer=customer
        ).order_by("-id")
        print("================")
        print("USER:", request.user)

        print("ORDERS:", customer_orders.count())
        print("================")
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

@manager_required
def category_list(request):

    return render(request, "category_list.html", {
        "categories": Category.objects.all()
    })


@manager_required
def add_category(request):

    if request.method == "POST":

        Category.objects.create(
            name=request.POST.get("name"),
            image=request.FILES.get("image"),
            status=request.POST.get("status")
        )

        return redirect('category_list')

    return render(request, "add_category.html")


@manager_required
def fooditem_detail(request, pk):

    item = get_object_or_404(FoodItem, pk=pk)

    total_sold = OrderItem.objects.filter(food_item=item).aggregate(
        total=Sum('quantity')
    )['total'] or 0

    return render(request, "fooditem_detail.html", {
        "item": item,
        "total_sold": total_sold
    })

@manager_required
def category_edit(request, pk):

    category = get_object_or_404(Category, pk=pk)

    if request.method == "POST":
        category.name = request.POST.get("name")
        category.save()
        return redirect("category_list")

    return render(request, "category_edit.html", {"category": category})


@manager_required
def category_delete(request, pk):

    get_object_or_404(Category, pk=pk).delete()
    return redirect('category_list')


# ---------------- DEALER ---------------- #

@manager_required
def dealer_list(request):

    return render(request, "dealer_list.html", {
        "dealers": Dealer.objects.all()
    })


@manager_required
def add_dealer(request):

    if request.method == "POST":
        Dealer.objects.create(
            name=request.POST.get("name"),
            phone=request.POST.get("phone"),
            address=request.POST.get("address")
        )
        return redirect("dealer_list")

    return render(request, "add_dealer.html")


@manager_required
def delete_dealer(request, id):

    dealer = get_object_or_404(Dealer, id=id)

    if request.method == "POST":
        dealer.delete()
        return redirect("dealer_list")

    return render(request, "confirm_delete.html", {"dealer": dealer})
# ---------------- FOOD ---------------- #

@employee_required
def fooditem_list(request):

    return render(request, "fooditem_list.html", {
        "items": FoodItem.objects.all()
    })


@manager_required
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

    FoodItem.objects.create(
        name=request.POST.get("name"),
        description=request.POST.get("description"),
        price=request.POST.get("price"),
        category=category,
        dealer=dealer,
        image=image
    )

    return redirect("fooditem_list")


@manager_required
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


@manager_required
def fooditem_delete(request, pk):

    item = get_object_or_404(FoodItem, pk=pk)
    item.delete()
    return redirect("fooditem_list")


@employee_required
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

@employee_required
def order_list(request):

    return render(request, "order_list.html", {
        "orders": Order.objects.all()
    })


@login_required
def order_detail(request, pk):

    order = get_object_or_404(Order, pk=pk)

    return render(request, "order_detail.html", {
        "order": order,
        "items": OrderItem.objects.filter(order=order)
    })

@login_required
def create_order(request):

    customers = Customer.objects.all()
    food_items = FoodItem.objects.all()

    if request.method == "POST":

        customer = get_object_or_404(
            Customer,
            id=request.POST.get("customer")
        )

        paid_amount = Decimal(request.POST.get("paid_amount") or 0)
        # 1️⃣ Create Order with payment info
        order = Order.objects.create(
    customer=customer,
    paid_amount=paid_amount,
    payment_status="Pending"
)

        food_ids = request.POST.getlist("food_item[]")
        quantities = request.POST.getlist("quantity[]")

        total_created = False

        for fid, qty in zip(food_ids, quantities):

            if not fid or not qty:
                continue

            food = get_object_or_404(FoodItem, id=fid)

            if food.quantity < int(qty):
                messages.error(request, "Stock issue")
                order.delete()
                return redirect("order_list")

            OrderItem.objects.create(
                order=order,
                food_item=food,
                quantity=int(qty)
            )

            food.quantity -= int(qty)
            food.save()

            total_created = True

        # agar koi item hi na ho
        if not total_created:
            order.delete()
            messages.error(request, "No items selected")
            return redirect("order_list")
        total_bill = order.total_price

        if order.paid_amount >= total_bill:
            order.payment_status = "Cleared"
        else:
            order.payment_status = "Pending"

        order.save()
        messages.success(request, "Order created successfully")
        return redirect("order_list")

    return render(request, "create_order.html", {
        "customers": customers,
        "food_items": food_items
    })
@manager_required
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

        return redirect("order_detail", pk=order.pk)

    return render(request, "order_edit.html", {"order": order})
@manager_required
def update_order_status(request, pk):
    order = get_object_or_404(Order, pk=pk)

    if request.method == "POST":
        status = request.POST.get("status")

        if status:   # 🔥 VERY IMPORTANT
            order.status = status
            order.save()

    return redirect("order_list")

@manager_required
def order_delete(request, pk):

    order = get_object_or_404(Order, pk=pk)

    if request.method == "POST":
        order.delete()
        return redirect("order_list")

    return render(request, "order_confirm_delete.html", {"order": order})



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
def global_search(request):
    q = request.GET.get("q", "")

    return render(request, "search_results.html", {
        "query": q,
        "food": FoodItem.objects.filter(name__icontains=q),
        "customers": Customer.objects.filter(name__icontains=q),
        "employees": Employee.objects.filter(first_name__icontains=q),
        "orders": Order.objects.filter(id__icontains=q),
})