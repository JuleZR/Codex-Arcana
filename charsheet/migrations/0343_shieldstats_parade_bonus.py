from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0342_item_invested_cp_steps"),
    ]

    operations = [
        migrations.AddField(
            model_name="shieldstats",
            name="parade_bonus",
            field=models.IntegerField(
                default=0,
                help_text="Bonus auf die Fertigkeit Schilde, wenn mit diesem Schild verteidigt wird.",
            ),
        ),
    ]
