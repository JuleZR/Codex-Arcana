from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0237_creature_special_knowledge_effect_value"),
    ]

    operations = [
        migrations.AlterField(
            model_name="creaturetraitchoicedefinition",
            name="allowed_derived_stat",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
