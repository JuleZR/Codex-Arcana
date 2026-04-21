from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0122_spell_duration_day"),
    ]

    operations = [
        migrations.AddField(
            model_name="spell",
            name="extra_cost",
            field=models.CharField(blank=True, default="", max_length=150, verbose_name="Zusatzkosten"),
        ),
    ]
