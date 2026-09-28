"""Time-limited, single-use email verification for application users."""

from smtplib import SMTPException
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models.user import UserSettings


TOKEN_SALT = "charsheet.email-verification"


def email_is_verified(user, user_settings=None):
    """Return whether the explicitly verified address is still current."""
    if not user.email:
        return False
    if user_settings is None:
        user_settings, _ = UserSettings.objects.get_or_create(user=user)
    return (
        user_settings.email_verified
        and user_settings.verified_email.casefold() == user.email.casefold()
    )


def request_email_verification(request, user):
    """Create and send a replacement token, respecting the resend cooldown."""
    email = (user.email or "").strip()
    if not email:
        return "unavailable"

    now = timezone.now()
    with transaction.atomic():
        locked_settings = UserSettings.objects.select_for_update()
        user_settings, _ = locked_settings.get_or_create(user=user)
        if email_is_verified(user, user_settings):
            return "already_verified"

        same_pending_address = (
            user_settings.email_verification_address.casefold()
            == email.casefold()
        )
        cooldown = settings.EMAIL_VERIFICATION_RESEND_COOLDOWN
        if (
            same_pending_address
            and user_settings.email_verification_sent_at
            and (
                now - user_settings.email_verification_sent_at
            ).total_seconds() < cooldown
        ):
            return "cooldown"

        nonce = uuid4()
        user_settings.email_verified = False
        user_settings.verified_email = ""
        user_settings.email_verification_address = email
        user_settings.email_verification_token = nonce
        user_settings.email_verification_sent_at = now
        user_settings.save(
            update_fields=[
                "email_verified",
                "verified_email",
                "email_verification_address",
                "email_verification_token",
                "email_verification_sent_at",
            ]
        )

    token = signing.dumps(
        {"user_id": user.pk, "email": email, "nonce": str(nonce)},
        salt=TOKEN_SALT,
        compress=True,
    )
    verification_url = request.build_absolute_uri(
        reverse("verify_email", kwargs={"token": token})
    )
    context = {
        "verification_url": verification_url,
        "timeout_seconds": settings.EMAIL_VERIFICATION_TIMEOUT,
    }
    subject = "".join(
        render_to_string(
            "registration/email_verification_subject.txt",
            context,
        ).splitlines()
    )
    body = render_to_string(
        "registration/email_verification_email.txt",
        context,
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email])
    except (OSError, SMTPException):
        return "delivery_failed"
    return "sent"


def verify_email_token(token):
    """Consume a valid token and return a public result status."""
    try:
        payload = signing.loads(
            token,
            salt=TOKEN_SALT,
            max_age=settings.EMAIL_VERIFICATION_TIMEOUT,
        )
    except signing.SignatureExpired:
        return "expired", None
    except (signing.BadSignature, TypeError, ValueError):
        return "invalid", None

    user_id = payload.get("user_id")
    email = payload.get("email")
    nonce = payload.get("nonce")
    if not user_id or not email or not nonce:
        return "invalid", None

    User = get_user_model()
    with transaction.atomic():
        user = User.objects.select_for_update().filter(pk=user_id).first()
        if user is None:
            return "invalid", None
        locked_settings = UserSettings.objects.select_for_update()
        user_settings, _ = locked_settings.get_or_create(user=user)
        if email_is_verified(user, user_settings):
            return "already_verified", user
        if (user.email or "").casefold() != str(email).casefold():
            return "changed", None
        pending_email = user_settings.email_verification_address.casefold()
        if pending_email != str(email).casefold():
            return "invalid", None
        if str(user_settings.email_verification_token) != str(nonce):
            return "invalid", None

        user_settings.email_verified = True
        user_settings.verified_email = user.email
        user_settings.email_verification_address = ""
        user_settings.email_verification_token = None
        user_settings.email_verification_sent_at = None
        user_settings.save(
            update_fields=[
                "email_verified",
                "verified_email",
                "email_verification_address",
                "email_verification_token",
                "email_verification_sent_at",
            ]
        )
    return "verified", user
