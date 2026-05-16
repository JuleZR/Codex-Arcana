from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0139_alter_characteritem_magic_effect_summary"),
    ]

    operations = [
        migrations.AddField(
            model_name="modifier",
            name="display_order",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
