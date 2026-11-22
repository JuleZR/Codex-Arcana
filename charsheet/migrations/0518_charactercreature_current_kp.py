from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0517_builder_attribute_scores")]

    operations = [
        migrations.AddField(
            model_name="charactercreature",
            name="current_kp",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
