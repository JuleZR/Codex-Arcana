from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0060_technique_target_choice_definition"),
    ]

    operations = [
        migrations.AddField(
            model_name="modifier",
            name="target_choice_definition",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="targeting_modifiers",
                to="charsheet.techniquechoicedefinition",
            ),
        ),
        migrations.AlterField(
            model_name="technique",
            name="target_choice_definition",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="targeting_techniques",
                to="charsheet.techniquechoicedefinition",
            ),
        ),
    ]
