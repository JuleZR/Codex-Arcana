from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0099_alter_item_item_type_magicitemstats"),
    ]

    operations = [
        migrations.AddField(
            model_name="modifier",
            name="effect_description",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
