from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0249_alter_itemownershipevent_event_type"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="character",
            name="current_damage",
        ),
        migrations.AddField(
            model_name="character",
            name="current_stun_damage",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="character",
            name="current_lethal_damage",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
