from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0234_creature_trait_choice_special_skill_category_flag"),
    ]

    operations = [
        migrations.AddField(
            model_name="charactercreature",
            name="combat_swimming_speed_override",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="charactercreature",
            name="march_swimming_speed_override",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="charactercreature",
            name="movement_mana_cost_override",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="charactercreature",
            name="movement_note_override",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="charactercreature",
            name="sprint_swimming_speed_override",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="charactercreature",
            name="combat_fly_speed_override",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="charactercreature",
            name="combat_speed_override",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="charactercreature",
            name="march_fly_speed_override",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="charactercreature",
            name="march_speed_override",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="charactercreature",
            name="natural_rs_override",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="charactercreature",
            name="sprint_fly_speed_override",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="charactercreature",
            name="sprint_speed_override",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="charactercreature",
            name="swimming_speed_override",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="charactercreature",
            name="wound_step_override",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
