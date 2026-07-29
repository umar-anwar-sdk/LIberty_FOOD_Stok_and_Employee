from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("people_app", "0005_employee_user")]

    operations = [
        migrations.AlterField(
            model_name="customer",
            name="email",
            field=models.EmailField(max_length=254, unique=True),
        ),
    ]
