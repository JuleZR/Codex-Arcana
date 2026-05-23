from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0150_character_spent_spell_learning_slots"),
    ]

    operations = [
        migrations.AddField(
            model_name="divineentity",
            name="grants_arcane_spell_choice_per_level",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Wenn aktiv, darf der Charakter pro Stufe in dieser goettlichen Schule "
                    "einen arkanen Zauber des exakt gleichen Grades waehlen."
                ),
            ),
        ),
        migrations.AddField(
            model_name="characterspell",
            name="granted_by_entity",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="granted_arcane_spells",
                to="charsheet.divineentity",
            ),
        ),
        migrations.AddField(
            model_name="characterspell",
            name="granted_for_level",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Stores the divine school level that unlocked this special granted spell.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="characterspell",
            name="ignore_critical_fumble_table",
            field=models.BooleanField(
                default=False,
                help_text="If true, critical failures with this spell skip the fumble table.",
            ),
        ),
        migrations.AddField(
            model_name="characterspell",
            name="uses_divine_school_level",
            field=models.BooleanField(
                default=False,
                help_text="If true, this spell uses the granting divine entity's school level as effective casting level.",
            ),
        ),
        migrations.AlterField(
            model_name="characterspell",
            name="source_kind",
            field=models.CharField(
                choices=[
                    ("arcane_free", "Arcane Free Choice"),
                    ("arcane_extra", "Arcane Extra Spell"),
                    ("arcane_bonus", "Arcane Bonus Spell"),
                    ("divine_granted", "Divine Granted"),
                    ("divine_arcane_granted", "Divine Arcane Granted"),
                    ("divine_extra", "Divine Extra Spell"),
                    ("divine_bonus", "Divine Bonus Spell"),
                    ("base", "Base Spell"),
                    ("manual", "Manual"),
                ],
                default="manual",
                max_length=30,
            ),
        ),
    ]
