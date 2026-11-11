from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0507_item_unequipped_effect_flags"),
    ]

    operations = [
        migrations.AddField(
            model_name="characteritem",
            name="base_values_are_size_adjusted_override",
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
