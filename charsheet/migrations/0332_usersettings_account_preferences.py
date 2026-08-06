from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0331_alter_item_item_type_magical_equipment"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersettings",
            name="theme_mode",
            field=models.CharField(
                choices=[
                    ("default", "Standard"),
                    ("compact", "Kompakt"),
                    ("large", "Groß"),
                    ("high_contrast", "Hoher Kontrast"),
                ],
                default="default",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="print_include_inventory",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="print_include_notes",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="print_compact",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="password_changed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
