from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0151_divine_entity_arcane_spell_rule"),
    ]

    operations = [
        migrations.AddField(
            model_name="divineentity",
            name="symbol_image",
            field=models.ImageField(
                blank=True,
                help_text="Optionales Symbolbild fuer diese goettliche Entitaet.",
                null=True,
                upload_to="divine_entities/",
            ),
        ),
    ]
