from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0185_characterdruidcult_custom_god_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="characterdruidcult",
            name="custom_description",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Character-specific description, taboo, form, or tradition notes.",
            ),
        ),
        migrations.AddField(
            model_name="characterdruidcult",
            name="custom_fluff",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Character-specific flavor quote for the personal druid card.",
            ),
        ),
        migrations.AddField(
            model_name="characterdruidcult",
            name="custom_g_ability",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Character-specific rules text for the personal druid card.",
            ),
        ),
        migrations.AddField(
            model_name="characterdruidcult",
            name="custom_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Character-specific card name for this druid circle.",
                max_length=160,
            ),
        ),
        migrations.AddField(
            model_name="characterdruidcult",
            name="tradition_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional character-specific druid circle or tradition name.",
                max_length=160,
            ),
        ),
    ]
