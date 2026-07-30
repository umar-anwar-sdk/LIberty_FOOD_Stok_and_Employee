"""Single source of truth for customer receivable ledger writes."""
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum

from .models import CustomerLedgerEntry, Payment


ZERO = Decimal("0.00")


def money(value):
    return Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@transaction.atomic
def sync_order_ledger(order):
    """Synchronise an order and all recorded payments to its ledger entries.

    The operation is idempotent, so repeating it cannot make duplicate
    transactions. It also repairs legacy orders whose paid total predates the
    Payment table by creating one clearly-labelled opening payment entry.
    """
    order.refresh_from_db()
    total = money(order.total_price)
    charge, _ = CustomerLedgerEntry.objects.update_or_create(
        order=order,
        entry_type="order",
        defaults={
            "customer": order.customer,
            "debit": total,
            "credit": ZERO,
            "description": f"Order #{order.pk}",
            "occurred_at": order.order_date,
        },
    )
    payment_total = ZERO
    for payment in Payment.objects.filter(order=order).order_by("created_at", "pk"):
        payment_total += money(payment.amount)
        CustomerLedgerEntry.objects.update_or_create(
            payment=payment,
            defaults={
                "customer": order.customer,
                "order": order,
                "entry_type": "payment",
                "debit": ZERO,
                "credit": money(payment.amount),
                "description": payment.note or f"Payment for order #{order.pk}",
                "occurred_at": payment.created_at,
            },
        )

    # Preserve prior data entered before Payment records were introduced.
    legacy_paid = max(ZERO, money(order.paid_amount) - payment_total)
    legacy = CustomerLedgerEntry.objects.filter(order=order, entry_type="adjustment", description="Opening recorded payment").first()
    if legacy_paid:
        CustomerLedgerEntry.objects.update_or_create(
            order=order, entry_type="adjustment",
            defaults={"customer": order.customer, "debit": ZERO, "credit": legacy_paid,
                      "description": "Opening recorded payment", "occurred_at": order.order_date},
        )
    elif legacy:
        legacy.delete()
    return charge


@transaction.atomic
def record_payment(order, amount, note=""):
    amount = money(amount)
    if amount <= ZERO:
        raise ValueError("Payment amount must be greater than zero.")
    if amount > money(order.remaining_amount):
        raise ValueError("Payment cannot exceed the outstanding balance.")
    payment = Payment.objects.create(order=order, amount=amount, note=note)
    order.paid_amount = money(order.paid_amount) + amount
    order.payment_status = "Cleared" if order.paid_amount >= money(order.total_price) else "Pending"
    order.save(update_fields=["paid_amount", "payment_status"])
    sync_order_ledger(order)
    return payment


def customer_ledger(customer, *, start=None, end=None, search=""):
    entries = CustomerLedgerEntry.objects.filter(customer=customer).select_related("order", "payment")
    if start:
        entries = entries.filter(occurred_at__date__gte=start)
    if end:
        entries = entries.filter(occurred_at__date__lte=end)
    if search:
        entries = entries.filter(description__icontains=search)
    return entries.order_by("occurred_at", "id")


def ledger_summary(customer):
    totals = CustomerLedgerEntry.objects.filter(customer=customer).aggregate(
        purchases=Sum("debit"), paid=Sum("credit")
    )
    purchases = money(totals["purchases"])
    paid = money(totals["paid"])
    return {"total_purchase": purchases, "total_paid": paid, "outstanding": purchases - paid}
