from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0272_creature_kp_and_remove_card_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamegroupcreature",
            name="current_kp",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
