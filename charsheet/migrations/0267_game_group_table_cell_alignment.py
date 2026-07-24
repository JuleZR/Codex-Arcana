from django.db import migrations, models


def preserve_number_alignment(apps, schema_editor):
    table_cell = apps.get_model("charsheet", "GameGroupTableCell")
    table_cell.objects.filter(value_type="number").update(alignment="center")


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0266_game_group_screen_note_is_visible"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamegrouptablecell",
            name="alignment",
            field=models.CharField(
                choices=[
                    ("left", "Linksbündig"),
                    ("center", "Zentriert"),
                    ("right", "Rechtsbündig"),
                ],
                default="left",
                max_length=6,
            ),
        ),
        migrations.RunPython(
            preserve_number_alignment,
            migrations.RunPython.noop,
        ),
    ]
