from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0429_migrate_spiritual_entities")]

    operations = [
        migrations.AlterField(
            model_name="divineentity",
            name="entity_type",
            field=models.ForeignKey(
                to="charsheet.divineentitytype",
                related_name="entities",
                on_delete=django.db.models.deletion.PROTECT,
            ),
        ),
        migrations.AlterField(
            model_name="druidcult",
            name="entity",
            field=models.ForeignKey(
                to="charsheet.divineentity",
                related_name="druid_cults",
                on_delete=django.db.models.deletion.PROTECT,
                limit_choices_to={"entity_type__slug": "power-animal"},
            ),
        ),
        migrations.AlterField(
            model_name="shamanpatron",
            name="entity",
            field=models.ForeignKey(
                to="charsheet.divineentity",
                related_name="shaman_patrons",
                on_delete=django.db.models.deletion.PROTECT,
            ),
        ),
        migrations.AlterModelOptions(
            name="shamanpatron",
            options={"ordering": ["entity__entity_type__name", "name"]},
        ),
        migrations.RemoveField("divineentity", "legacy_pantheon"),
        migrations.RemoveField("shamanpatron", "patron_kind"),
    ] + [
        migrations.RemoveField(model_name, field)
        for model_name in ("druidcult", "shamanpatron")
        for field in (
            "card_name",
            "description",
            "g_ability",
            "fluff",
            "symbol_image",
            "god_image",
        )
    ]
