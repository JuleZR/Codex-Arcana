from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0489_organization_name_connector"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="organization",
            name="name_connector",
        ),
    ]
