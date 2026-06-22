from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0197_charactershamanpatron_card_customization")]

    operations = [
        migrations.AddField(
            model_name="charactershamanpatron",
            name="patron_kind_override",
            field=models.CharField(
                blank=True,
                choices=[("totem", "Totem"), ("ancestor_spirit", "Ahnengeist")],
                default="",
                max_length=24,
            ),
        ),
    ]
