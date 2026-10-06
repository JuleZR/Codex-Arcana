import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0443_divine_school_entity_types"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Metal",
            new_name="Material",
        ),
        migrations.RenameField(
            model_name="item",
            old_name="metal",
            new_name="material",
        ),
        migrations.AlterField(
            model_name="material",
            name="quality_overwrite",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="material_overwrites",
                to="charsheet.quality",
            ),
        ),
        migrations.AlterField(
            model_name="material",
            name="apply_quality_effects",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Wenn deaktiviert, überschreibt das Material die "
                    "angezeigte Qualität, ohne deren regeltechnische "
                    "Qualitätsboni anzuwenden."
                ),
            ),
        ),
    ]
