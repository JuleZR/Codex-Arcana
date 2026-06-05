from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0176_alter_spell_range_unit_add_hearing"),
    ]

    operations = [
        migrations.AddField(
            model_name="spell",
            name="duration2_text",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
