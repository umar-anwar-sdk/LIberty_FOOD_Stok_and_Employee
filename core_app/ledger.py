"""Single source of truth for customer receivable ledger writes."""
from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from .models import CustomerLedgerEntry, CustomerManualLedgerEntry, Order, Payment, WalkingCustomerLedgerEntry


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
    if order.walking_customer is not None:
        ledger_model = WalkingCustomerLedgerEntry
        ledger_kwargs = {
            "walking_customer": order.walking_customer,
        }
    elif order.customer is not None:
        ledger_model = CustomerLedgerEntry
        ledger_kwargs = {
            "customer": order.customer,
        }
    else:
        return None

    charge, _ = ledger_model.objects.update_or_create(
        order=order,
        entry_type="order",
        defaults={
            **ledger_kwargs,
            "debit": total,
            "credit": ZERO,
            "description": f"Order #{order.pk}",
            "occurred_at": order.order_date,
        },
    )
    payment_total = ZERO
    for payment in Payment.objects.filter(order=order).order_by("created_at", "pk"):
        payment_total += money(payment.amount)
        ledger_model.objects.update_or_create(
            payment=payment,
            defaults={
                **ledger_kwargs,
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
    legacy = ledger_model.objects.filter(order=order, entry_type="adjustment", description="Opening recorded payment").first()
    if legacy_paid:
        ledger_model.objects.update_or_create(
            order=order, entry_type="adjustment",
            defaults={
                **ledger_kwargs,
                "debit": ZERO,
                "credit": legacy_paid,
                "description": "Opening recorded payment",
                "occurred_at": order.order_date,
            },
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
    entries = list(CustomerLedgerEntry.objects.filter(customer=customer).select_related("order", "payment"))
    manual_entries = CustomerManualLedgerEntry.objects.filter(customer=customer)
    if start:
        manual_entries = manual_entries.filter(entry_date__gte=start)
        entries = [entry for entry in entries if entry.occurred_at.date() >= start]
    if end:
        manual_entries = manual_entries.filter(entry_date__lte=end)
        entries = [entry for entry in entries if entry.occurred_at.date() <= end]
    if search:
        entries = [entry for entry in entries if search.lower() in (entry.description or "").lower()]
        manual_entries = manual_entries.filter(Q(notes__icontains=search) | Q(entry_type__icontains=search))

    for manual_entry in manual_entries:
        entries.append(
            type(
                "LedgerEntryView",
                (),
                {
                    "debit": money(manual_entry.amount) if manual_entry.entry_type == "debit" else ZERO,
                    "credit": money(manual_entry.amount) if manual_entry.entry_type == "credit" else ZERO,
                    "description": "Manual Ledger Entry" if not manual_entry.notes.strip() else f"Manual Ledger Entry - {manual_entry.notes.strip()}",
                    "occurred_at": timezone.make_aware(datetime.combine(manual_entry.entry_date, time.min)),
                    "id": f"manual-{manual_entry.pk}",
                },
            )()
        )

    entries.sort(key=lambda entry: (entry.occurred_at, str(entry.id)))
    return entries


def customer_ledger_summary(customer):
    totals = CustomerLedgerEntry.objects.filter(customer=customer).aggregate(
        purchases=Sum("debit"), paid=Sum("credit")
    )
    manual_totals = CustomerManualLedgerEntry.objects.filter(customer=customer).aggregate(
        purchases=Sum("amount", filter=Q(entry_type="debit")),
        paid=Sum("amount", filter=Q(entry_type="credit")),
    )
    purchases = money(totals["purchases"]) + money(manual_totals["purchases"])
    paid = money(totals["paid"]) + money(manual_totals["paid"])
    return {"total_purchase": purchases, "total_paid": paid, "outstanding": purchases - paid}


@transaction.atomic
def sync_manual_ledger_entry(entry):
    """Mirror a manual customer ledger entry into the database-backed Khata/ledger."""
    if not isinstance(entry, CustomerManualLedgerEntry):
        entry = CustomerManualLedgerEntry.objects.get(pk=entry.pk)

    occurred_at = timezone.make_aware(datetime.combine(entry.entry_date, time.min))
    description = "Manual Ledger Entry"
    if entry.notes.strip():
        description = f"Manual Ledger Entry - {entry.notes.strip()}"

    debit = money(entry.amount) if entry.entry_type == "debit" else ZERO
    credit = money(entry.amount) if entry.entry_type == "credit" else ZERO

    CustomerLedgerEntry.objects.update_or_create(
        customer=entry.customer,
        description=description,
        occurred_at=occurred_at,
        defaults={
            "order": None,
            "payment": None,
            "entry_type": "adjustment",
            "debit": debit,
            "credit": credit,
        },
    )
    return description


def ledger_summary(customer):
    """Backward-compatible alias used by the app's customer account views."""
    return customer_ledger_summary(customer)


@transaction.atomic
def create_manual_customer_order(customer, order_date, bill_amount, paid_amount, notes, bill_snapshot=None):
    order = Order.objects.create(
        customer=customer,
        manual_order=True,
        manual_order_amount=bill_amount,
        bill_snapshot=bill_snapshot,
        notes=notes or "Manual Order",
        order_date=order_date,
        paid_amount=paid_amount,
        payment_status="Cleared" if paid_amount >= bill_amount else "Pending",
    )
    if paid_amount:
        Payment.objects.create(order=order, amount=paid_amount, note="Manual order payment")
        order.payment_status = "Cleared" if paid_amount >= bill_amount else "Pending"
        order.save(update_fields=["payment_status"])
    sync_order_ledger(order)
    return order
    sync_order_ledger(order)
    return order


def walking_customer_ledger(walking_customer, *, start=None, end=None, search=""):
    entries = WalkingCustomerLedgerEntry.objects.filter(walking_customer=walking_customer).select_related("order", "payment")
    if start:
        entries = entries.filter(occurred_at__date__gte=start)
    if end:
        entries = entries.filter(occurred_at__date__lte=end)
    if search:
        entries = entries.filter(description__icontains=search)
    return entries.order_by("occurred_at", "id")


def walking_ledger_summary(walking_customer):
    totals = WalkingCustomerLedgerEntry.objects.filter(walking_customer=walking_customer).aggregate(
        purchases=Sum("debit"), paid=Sum("credit")
    )
    purchases = money(totals["purchases"])
    paid = money(totals["paid"])
    return {"total_purchase": purchases, "total_paid": paid, "outstanding": purchases - paid}
