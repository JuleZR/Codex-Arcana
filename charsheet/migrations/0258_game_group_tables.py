from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0257_character_carry_load_enabled"),
    ]

    operations = [
        migrations.CreateModel(
            name="GameGroupTable",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=150)),
                ("position", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="data_tables",
                        to="charsheet.gamegroup",
                    ),
                ),
            ],
            options={"ordering": ["position", "id"]},
        ),
        migrations.CreateModel(
            name="GameGroupTableColumn",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("heading", models.CharField(max_length=100)),
                ("position", models.PositiveIntegerField(default=0)),
                (
                    "table",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="columns",
                        to="charsheet.gamegrouptable",
                    ),
                ),
            ],
            options={"ordering": ["position", "id"]},
        ),
        migrations.CreateModel(
            name="GameGroupTableRow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField(default=0)),
                (
                    "table",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rows",
                        to="charsheet.gamegrouptable",
                    ),
                ),
            ],
            options={"ordering": ["position", "id"]},
        ),
        migrations.CreateModel(
            name="GameGroupTableCell",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "value_type",
                    models.CharField(
                        choices=[("text", "Text"), ("number", "Zahl")],
                        default="text",
                        max_length=10,
                    ),
                ),
                ("text_value", models.TextField(blank=True, default="")),
                ("number_value", models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                (
                    "column",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cells",
                        to="charsheet.gamegrouptablecolumn",
                    ),
                ),
                (
                    "row",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cells",
                        to="charsheet.gamegrouptablerow",
                    ),
                ),
            ],
            options={"ordering": ["row__position", "column__position", "id"]},
        ),
        migrations.AddConstraint(
            model_name="gamegrouptablecolumn",
            constraint=models.UniqueConstraint(
                fields=("table", "position"),
                name="uniq_game_group_table_column_position",
            ),
        ),
        migrations.AddConstraint(
            model_name="gamegrouptablerow",
            constraint=models.UniqueConstraint(
                fields=("table", "position"),
                name="uniq_game_group_table_row_position",
            ),
        ),
        migrations.AddConstraint(
            model_name="gamegrouptablecell",
            constraint=models.UniqueConstraint(
                fields=("row", "column"),
                name="uniq_game_group_table_cell",
            ),
        ),
    ]
