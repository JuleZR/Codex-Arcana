from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0391_traitspecificationoption_and_more")]

    operations = [
        migrations.AddField(
            model_name="spell",
            name="is_divine_extra",
            field=models.BooleanField(
                default=False),
        ),
        migrations.AddField(
            model_name="spell",
            name="divine_entities",
            field=models.ManyToManyField(
                blank=True,
                related_name="restricted_spells",
                to="charsheet.divineentity",
            ),
        ),
    ]
