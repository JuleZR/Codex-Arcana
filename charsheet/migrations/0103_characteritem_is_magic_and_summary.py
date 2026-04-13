from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0102_alter_character_current_arcane_power_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="characteritem",
            name="is_magic",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="characteritem",
            name="magic_effect_summary",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
