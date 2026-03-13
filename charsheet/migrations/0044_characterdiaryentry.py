from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0043_characterskill_specification"),
    ]

    operations = [
        migrations.CreateModel(
            name="CharacterDiaryEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order_index", models.PositiveIntegerField(default=0)),
                ("text", models.TextField(blank=True, default="")),
                ("entry_date", models.DateField(blank=True, null=True)),
                ("is_fixed", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="diary_entries",
                        to="charsheet.character",
                    ),
                ),
            ],
            options={
                "ordering": ["character", "order_index", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="characterdiaryentry",
            constraint=models.UniqueConstraint(
                fields=("character", "order_index"),
                name="uniq_character_diary_entry_order",
            ),
        ),
    ]
