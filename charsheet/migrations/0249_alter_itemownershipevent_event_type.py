from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0248_merge_compatible_character_item_stacks"),
    ]

    operations = [
        migrations.AlterField(
            model_name="itemownershipevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("created", "Übergabe erstellt"),
                    ("accepted", "Übergabe angenommen"),
                    ("declined", "Übergabe abgelehnt"),
                    ("expired", "Automatisch zurückgegeben"),
                    ("recalled", "Übergabe zurückgerufen"),
                    ("returned", "An Eigentümer zurückgegeben"),
                    ("enforced", "Zwangsvollstreckung"),
                    ("permission_granted", "Recht erteilt"),
                    ("permission_revoked", "Recht widerrufen"),
                    ("permission_invalidated", "Recht durch Besitzerwechsel beendet"),
                    ("destroyed", "Item endgültig entfernt"),
                ],
                max_length=32,
            ),
        ),
    ]
