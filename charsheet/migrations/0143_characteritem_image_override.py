from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0142_rune_short_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="characteritem",
            name="image_override",
            field=models.ImageField(blank=True, null=True, upload_to="character_items/"),
        ),
    ]
