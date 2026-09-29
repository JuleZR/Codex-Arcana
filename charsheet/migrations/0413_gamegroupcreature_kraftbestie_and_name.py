from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0412_passkey_credentials"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamegroupcreature",
            name="is_kraftbestie",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="gamegroupcreature",
            name="name_override",
            field=models.CharField(blank=True, max_length=160),
        ),
    ]
