from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0184_charactershamanpatron_shamanpatron_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="characterdruidcult",
            name="custom_god_image",
            field=models.ImageField(
                blank=True,
                help_text="Character-specific card image for this druid circle.",
                null=True,
                upload_to="character_druid_cults/",
            ),
        ),
    ]
