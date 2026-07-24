from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0261_game_group_table_cell_number_suffix"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamegroupmembership",
            name="screen_position",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
