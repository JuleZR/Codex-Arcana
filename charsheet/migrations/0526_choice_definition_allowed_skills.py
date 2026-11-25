from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0525_repeatable_trait_instances"),
    ]

    operations = [
        migrations.AddField(
            model_name=model_name,
            name="allowed_skills",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "Nur diese Fähigkeiten stehen zur Wahl. "
                    "Leer = keine feste Liste. "
                    "Kategorie und Familie gelten zusätzlich."
                ),
                related_name="+",
                to="charsheet.skill",
                verbose_name="Erlaubte Fähigkeiten",
            ),
        )
        for model_name in (
            "racechoicedefinition",
            "specializationchoicedefinition",
            "techniquechoicedefinition",
            "traitchoicedefinition",
        )
    ]
