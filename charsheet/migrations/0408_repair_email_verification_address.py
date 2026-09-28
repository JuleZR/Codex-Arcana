from django.db import migrations


def add_missing_email_verification_address(apps, schema_editor):
    UserSettings = apps.get_model("charsheet", "UserSettings")
    table_name = UserSettings._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        introspection = schema_editor.connection.introspection
        description = introspection.get_table_description(
            cursor,
            table_name,
        )
    column_names = {column.name for column in description}
    if "email_verification_address" not in column_names:
        field = UserSettings._meta.get_field("email_verification_address")
        schema_editor.add_field(UserSettings, field)


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0407_usersettings_email_verification"),
    ]

    operations = [
        migrations.RunPython(
            add_missing_email_verification_address,
            migrations.RunPython.noop,
        ),
    ]
