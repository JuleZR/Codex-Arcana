from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0260_game_group_table_cell_number_show_plus"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamegrouptablecell",
            name="number_suffix",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
