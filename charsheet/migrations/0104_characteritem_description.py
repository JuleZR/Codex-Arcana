from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0103_characteritem_is_magic_and_summary"),
    ]

    operations = [
        migrations.AddField(
            model_name="characteritem",
            name="description",
            field=models.TextField(blank=True, default=""),
        ),
    ]
