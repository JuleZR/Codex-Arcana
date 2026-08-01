import django.db.models.deletion
from django.db import migrations, models


def require_complete_vampire_powers(apps, schema_editor):
    VampirePower = apps.get_model("charsheet", "VampirePower")
    incomplete = list(
        VampirePower.objects.filter(weakness__isnull=True)
        .order_by("id")
        .values_list("slug", flat=True)
    )
    if incomplete:
        joined = ", ".join(incomplete)
        raise RuntimeError(
            "Every VampirePower needs an associated weakness before this migration can finish: "
            f"{joined}"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0319_finalize_vampire_power_split"),
    ]

    operations = [
        migrations.RunPython(require_complete_vampire_powers, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="vampirepower",
            name="weakness",
            field=models.ForeignKey(
                limit_choices_to={"trait_type": "disadvantage"},
                on_delete=django.db.models.deletion.PROTECT,
                related_name="associated_powers",
                to="charsheet.vampiretrait",
            ),
        ),
    ]
