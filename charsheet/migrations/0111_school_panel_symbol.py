from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0110_spell_panel_badge_label"),
    ]

    operations = [
        migrations.AddField(
            model_name="school",
            name="panel_symbol",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional short symbol shown in spell and school panels, for example a rune or glyph.",
                max_length=8,
            ),
        ),
    ]
