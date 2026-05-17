from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0141_item_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="rune",
            name="short_description",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
