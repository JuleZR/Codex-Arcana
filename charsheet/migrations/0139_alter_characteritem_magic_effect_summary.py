from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0138_alter_characterweaponmastery_options"),
    ]

    operations = [
        migrations.AlterField(
            model_name="characteritem",
            name="magic_effect_summary",
            field=models.TextField(blank=True, default=""),
        ),
    ]
