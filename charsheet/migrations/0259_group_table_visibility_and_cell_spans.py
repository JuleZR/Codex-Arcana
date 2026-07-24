from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0258_game_group_tables"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamegrouptable",
            name="is_visible",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddField(
            model_name="gamegrouptablecell",
            name="row_span",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="gamegrouptablecell",
            name="column_span",
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
