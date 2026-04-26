from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0125_spell_structured_extra_cost"),
    ]

    operations = [
        migrations.AlterField(
            model_name="modifier",
            name="target_kind",
            field=models.CharField(
                choices=[
                    ("skill", "Skill"),
                    ("category", "Skill Category"),
                    ("attribute", "Attribute"),
                    ("stat", "Stat"),
                    ("item", "Item"),
                    ("item_category", "Item Category"),
                    ("specialization", "Specialization"),
                    ("entity", "Other Entity"),
                ],
                max_length=30,
            ),
        ),
    ]
