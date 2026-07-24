from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0267_game_group_table_cell_alignment"),
    ]

    operations = [
        migrations.CreateModel(
            name="GameGroupCreature",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "screen_position",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                (
                    "screen_is_collapsed",
                    models.BooleanField(default=False),
                ),
                (
                    "current_damage",
                    models.PositiveIntegerField(default=0),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "creature",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="game_group_screen_instances",
                        to="charsheet.creature",
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="screen_creatures",
                        to="charsheet.gamegroup",
                    ),
                ),
            ],
            options={
                "ordering": ["group", "screen_position", "id"],
            },
        ),
    ]
