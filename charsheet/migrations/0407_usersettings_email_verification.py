from django.conf import settings
from django.db import migrations, models


def mark_existing_addresses_verified(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    UserSettings = apps.get_model("charsheet", "UserSettings")

    for user in User.objects.exclude(email="").iterator():
        user_settings, _ = UserSettings.objects.get_or_create(user_id=user.pk)
        user_settings.email_verified = True
        user_settings.verified_email = user.email
        user_settings.save(update_fields=["email_verified", "verified_email"])


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0406_normalize_pdf_text_artifacts"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersettings",
            name="email_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="verified_email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="email_verification_address",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="email_verification_token",
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="email_verification_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(
            mark_existing_addresses_verified,
            migrations.RunPython.noop,
        ),
    ]
