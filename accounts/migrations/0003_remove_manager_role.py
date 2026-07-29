from django.db import migrations, models


def convert_manager_roles(apps, schema_editor):
    # "Manager" was the legacy staff role.  Management is now admin-only.
    User = apps.get_model("accounts", "CustomUser")
    User.objects.filter(role="manager").update(role="admin")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_customuser_profile_image")]

    operations = [
        migrations.RunPython(convert_manager_roles, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="customuser",
            name="role",
            field=models.CharField(
                choices=[("admin", "Admin"), ("employee", "Employee"), ("customer", "Customer")],
                default="customer",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="customuser",
            name="email",
            field=models.EmailField(max_length=254, unique=True),
        ),
    ]
