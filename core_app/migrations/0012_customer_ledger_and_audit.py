from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core_app", "0011_order_paid_amount_order_payment_status"), ("people_app", "0007_customer_ledger_and_audit")]
    operations = [
        migrations.AddField(model_name="orderitem", name="unit_price", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        migrations.CreateModel(
            name="CustomerLedgerEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entry_type", models.CharField(choices=[("order", "Order charge"), ("payment", "Payment received"), ("refund", "Refund"), ("adjustment", "Adjustment")], max_length=20)),
                ("debit", models.DecimalField(decimal_places=2, default=0, max_digits=12)), ("credit", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("description", models.CharField(blank=True, max_length=255)), ("occurred_at", models.DateTimeField()), ("created_at", models.DateTimeField(auto_now_add=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ledger_entries", to="people_app.customer")),
                ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="ledger_entries", to="core_app.order")),
                ("payment", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="ledger_entry", to="core_app.payment")),
            ], options={"ordering": ("occurred_at", "id")},
        ),
        migrations.AddIndex(model_name="customerledgerentry", index=models.Index(fields=["customer", "occurred_at"], name="core_app_custome_1e345c_idx")),
        migrations.AddConstraint(model_name="customerledgerentry", constraint=models.UniqueConstraint(fields=("order", "entry_type"), name="one_order_charge_per_order_type")),
    ]
