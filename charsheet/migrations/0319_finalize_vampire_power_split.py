from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0318_split_vampire_traits_and_powers"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="charactercreaturevampiretrait",
            name="associated_weakness_bought_off",
        ),
        migrations.RemoveField(model_name="charactercreaturevampiretrait", name="rank"),
        migrations.RemoveField(
            model_name="charactervampiretrait",
            name="associated_weakness_bought_off",
        ),
        migrations.RemoveField(model_name="charactervampiretrait", name="rank"),
        migrations.RemoveField(
            model_name="creaturevampiretrait",
            name="associated_weakness_bought_off",
        ),
        migrations.RemoveField(model_name="creaturevampiretrait", name="rank"),
        migrations.RemoveField(
            model_name="gamegroupcreaturevampiretrait",
            name="associated_weakness_bought_off",
        ),
        migrations.RemoveField(model_name="gamegroupcreaturevampiretrait", name="rank"),
        migrations.RemoveField(model_name="vampiretrait", name="associated_weakness"),
        migrations.RemoveField(model_name="vampiretrait", name="blood_cost"),
        migrations.RemoveField(model_name="vampiretrait", name="handler"),
        migrations.RemoveField(model_name="vampiretrait", name="max_rank"),
        migrations.RemoveField(model_name="vampiretrait", name="point_value"),
        migrations.RemoveField(model_name="vampiretrait", name="rankable"),
        migrations.RemoveField(model_name="vampiretrait", name="rules_text"),
        migrations.AlterField(
            model_name="vampiretrait",
            name="trait_type",
            field=models.CharField(
                choices=[("advantage", "Advantage"), ("disadvantage", "Disadvantage")],
                max_length=20,
            ),
        ),
    ]
