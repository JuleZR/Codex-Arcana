from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0127_itemrune_modifier_sources"),
    ]

    operations = [
        migrations.AlterField(
            model_name="rune",
            name="allow_multiple",
            field=models.BooleanField(
                default=False,
                help_text="Wenn aktiv, darf diese Rune mehrfach auf demselben Gegenstand angebracht werden.",
            ),
        ),
    ]
