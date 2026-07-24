from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0259_group_table_visibility_and_cell_spans"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamegrouptablecell",
            name="number_show_plus",
            field=models.BooleanField(default=False),
        ),
    ]
