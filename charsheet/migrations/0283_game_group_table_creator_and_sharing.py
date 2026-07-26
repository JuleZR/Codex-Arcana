from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def assign_existing_table_creators(apps, schema_editor):
    game_group_table = apps.get_model("charsheet", "GameGroupTable")
    for data_table in game_group_table.objects.select_related("group").iterator():
        data_table.creator_id = data_table.group.creator_id
        data_table.save(update_fields=["creator"])


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0282_game_group_table_stacked"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="gamegrouptable",
            name="creator",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="created_game_group_tables",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="gamegrouptable",
            name="is_shared",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.RunPython(
            assign_existing_table_creators,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="gamegrouptable",
            name="creator",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="created_game_group_tables",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
