from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0427_artifact_investment_label")]

    operations = [
        migrations.CreateModel(
            name="DivineEntityType",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        primary_key=True,
                        serialize=False,
                        auto_created=True,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=120, unique=True)),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("description", models.TextField(blank=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Pantheon",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        primary_key=True,
                        serialize=False,
                        auto_created=True,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=160, unique=True)),
                ("slug", models.SlugField(max_length=160, unique=True)),
                ("description", models.TextField(blank=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.RenameField("divineentity", "pantheon", "legacy_pantheon"),
        migrations.AddField(
            model_name="divineentity",
            name="pantheon",
            field=models.ForeignKey(
                to="charsheet.pantheon",
                null=True,
                blank=True,
                related_name="entities",
                on_delete=django.db.models.deletion.PROTECT,
            ),
        ),
        migrations.AddField(
            model_name="divineentity",
            name="entity_type",
            field=models.ForeignKey(
                to="charsheet.divineentitytype",
                null=True,
                related_name="entities",
                on_delete=django.db.models.deletion.PROTECT,
            ),
        ),
        migrations.AlterField(
            model_name="divineentity",
            name="school",
            field=models.ForeignKey(
                to="charsheet.school",
                null=True,
                blank=True,
                related_name="divine_entities",
                on_delete=django.db.models.deletion.CASCADE,
                help_text=(
                    "Optional divine school; spiritual progression "
                    "is configured separately."
                ),
            ),
        ),
        migrations.AddField(
            model_name="druidcult",
            name="entity",
            field=models.ForeignKey(
                to="charsheet.divineentity",
                null=True,
                related_name="druid_cults",
                on_delete=django.db.models.deletion.PROTECT,
                limit_choices_to={"entity_type__slug": "power-animal"},
            ),
        ),
        migrations.AddField(
            model_name="shamanpatron",
            name="entity",
            field=models.ForeignKey(
                to="charsheet.divineentity",
                null=True,
                related_name="shaman_patrons",
                on_delete=django.db.models.deletion.PROTECT,
            ),
        ),
    ]
