from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0140_modifier_display_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="items/"),
        ),
    ]
