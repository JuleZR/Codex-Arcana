from django.db import migrations, models


def enable_ursprung_customization(apps, schema_editor):
    ShamanPatron = apps.get_model("charsheet", "ShamanPatron")
    ShamanPatron.objects.filter(slug="ursprung").update(is_customizable=True)


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0196_remove_creaturecardtemplateattack_template_and_more")]

    operations = [
        migrations.AddField(model_name="charactershamanpatron", name="custom_name", field=models.CharField(blank=True, default="", max_length=160)),
        migrations.AddField(model_name="charactershamanpatron", name="tradition_name", field=models.CharField(blank=True, default="", max_length=160)),
        migrations.AddField(model_name="charactershamanpatron", name="custom_description", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="charactershamanpatron", name="custom_g_ability", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="charactershamanpatron", name="custom_fluff", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="charactershamanpatron", name="custom_god_image", field=models.ImageField(blank=True, null=True, upload_to="character_shaman_patrons/")),
        migrations.RunPython(enable_ursprung_customization, migrations.RunPython.noop),
    ]
