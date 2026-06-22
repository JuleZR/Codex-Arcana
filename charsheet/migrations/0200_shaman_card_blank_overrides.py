from django.db import migrations, models


def preserve_existing_fallbacks(apps, schema_editor):
    CharacterShamanPatron = apps.get_model("charsheet", "CharacterShamanPatron")
    for field_name in (
        "custom_name",
        "tradition_name",
        "custom_description",
        "custom_g_ability",
        "custom_fluff",
    ):
        CharacterShamanPatron.objects.filter(**{field_name: ""}).update(**{field_name: None})


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0199_replace_shaman_patron_aspects_with_m2m")]

    operations = [
        migrations.AlterField(
            model_name="charactershamanpatron",
            name="custom_name",
            field=models.CharField(blank=True, default=None, max_length=160, null=True),
        ),
        migrations.AlterField(
            model_name="charactershamanpatron",
            name="tradition_name",
            field=models.CharField(blank=True, default=None, max_length=160, null=True),
        ),
        migrations.AlterField(
            model_name="charactershamanpatron",
            name="custom_description",
            field=models.TextField(blank=True, default=None, null=True),
        ),
        migrations.AlterField(
            model_name="charactershamanpatron",
            name="custom_g_ability",
            field=models.TextField(blank=True, default=None, null=True),
        ),
        migrations.AlterField(
            model_name="charactershamanpatron",
            name="custom_fluff",
            field=models.TextField(blank=True, default=None, null=True),
        ),
        migrations.RunPython(preserve_existing_fallbacks, migrations.RunPython.noop),
    ]
