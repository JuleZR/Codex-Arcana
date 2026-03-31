from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0077_rune_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="characteritem",
            name="runes",
            field=models.ManyToManyField(blank=True, related_name="character_items", to="charsheet.rune"),
        ),
    ]
