from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0497_trait_allowed_races")]

    operations = [
        migrations.AddField(
            model_name="characteritem",
            name="item_type_override",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="character_item_overrides",
                to="charsheet.itemtype",
            ),
        ),
    ]
