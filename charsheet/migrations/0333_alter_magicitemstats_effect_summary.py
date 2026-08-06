from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0332_usersettings_account_preferences"),
    ]

    operations = [
        migrations.AlterField(
            model_name="magicitemstats",
            name="effect_summary",
            field=models.TextField(blank=True, default=""),
        ),
    ]
