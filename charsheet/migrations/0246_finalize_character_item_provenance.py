import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0245_backfill_character_item_provenance"),
    ]

    operations = [
        migrations.AlterField(
            model_name="characteritem",
            name="original_owner_character",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="originally_owned_items",
                to="charsheet.character",
            ),
        ),
        migrations.AlterField(
            model_name="characteritem",
            name="provenance_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
