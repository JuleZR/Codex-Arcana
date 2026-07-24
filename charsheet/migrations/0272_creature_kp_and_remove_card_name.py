from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0271_game_group_creature_character_creature"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="creature",
            name="card_name",
        ),
        migrations.AddField(
            model_name="creature",
            name="has_kp",
            field=models.BooleanField(default=False, verbose_name="Hat KP"),
        ),
        migrations.AddField(
            model_name="creature",
            name="kp_override",
            field=models.IntegerField(blank=True, null=True, verbose_name="KP-Override"),
        ),
        migrations.AddField(
            model_name="creature",
            name="potential_override",
            field=models.IntegerField(blank=True, null=True, verbose_name="Potential-Override"),
        ),
    ]
