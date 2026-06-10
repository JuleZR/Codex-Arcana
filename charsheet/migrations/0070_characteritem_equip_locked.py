from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0069_racestartingitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="characteritem",
            name="equip_locked",
            field=models.BooleanField(default=False),
        ),
    ]
