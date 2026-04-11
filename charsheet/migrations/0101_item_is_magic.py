from django.db import migrations, models


def mark_existing_magic_items(apps, schema_editor):
    Item = apps.get_model("charsheet", "Item")
    Item.objects.filter(item_type="magic_item").update(is_magic=True)


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0100_modifier_effect_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="is_magic",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_existing_magic_items, migrations.RunPython.noop),
    ]
