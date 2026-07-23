from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0256_itemtransfer_accepted_by_user_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="character",
            name="carry_load_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
