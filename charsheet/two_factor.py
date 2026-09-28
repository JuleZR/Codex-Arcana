"""TOTP and recovery-code helpers for optional account two-factor auth."""

import base64
import hashlib
import io
import secrets

import pyotp
import qrcode
import qrcode.image.svg
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from .models import TwoFactorRecoveryCode


RECOVERY_CODE_COUNT = 10
RECOVERY_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def _fernet_key(secret_key):
    digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _secret_cipher():
    secret_keys = [settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS]
    return MultiFernet([Fernet(_fernet_key(key)) for key in secret_keys])


@sensitive_variables("secret")
def encrypt_totp_secret(secret):
    return _secret_cipher().encrypt(secret.encode("ascii")).decode("ascii")


@sensitive_variables("encrypted_secret")
def decrypt_totp_secret(encrypted_secret):
    try:
        return _secret_cipher().decrypt(
            encrypted_secret.encode("ascii")
        ).decode("ascii")
    except (InvalidToken, UnicodeError, ValueError):
        return ""


def generate_totp_secret():
    return pyotp.random_base32()


@sensitive_variables("secret")
def provisioning_uri(secret, user):
    account_name = user.email or user.get_username()
    return pyotp.TOTP(secret).provisioning_uri(
        name=account_name,
        issuer_name="Codex Arcana",
    )


@sensitive_variables("uri")
def provisioning_qr_data_uri(uri):
    image = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
    output = io.BytesIO()
    image.save(output)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


@sensitive_variables("secret", "code", "normalized")
def verify_totp(secret, code):
    normalized = "".join(
        character for character in code if character.isdigit()
    )
    if len(normalized) != 6:
        return False
    return pyotp.TOTP(secret).verify(normalized, valid_window=1)


def _new_recovery_code():
    raw = "".join(
        secrets.choice(RECOVERY_CODE_ALPHABET) for _ in range(12)
    )
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


@transaction.atomic
@sensitive_variables("codes")
def regenerate_recovery_codes(user):
    codes = [_new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    TwoFactorRecoveryCode.objects.filter(user=user).delete()
    TwoFactorRecoveryCode.objects.bulk_create(
        [
            TwoFactorRecoveryCode(user=user, code_hash=make_password(code))
            for code in codes
        ]
    )
    return codes


@transaction.atomic
@sensitive_variables("submitted_code", "normalized")
def consume_recovery_code(user, submitted_code):
    normalized = submitted_code.strip().upper()
    if not normalized:
        return False
    recovery_codes = TwoFactorRecoveryCode.objects.select_for_update().filter(
        user=user,
        used_at__isnull=True,
    )
    for recovery_code in recovery_codes:
        if check_password(normalized, recovery_code.code_hash):
            recovery_code.used_at = timezone.now()
            recovery_code.save(update_fields=["used_at"])
            return True
    return False


def unused_recovery_code_count(user):
    return TwoFactorRecoveryCode.objects.filter(
        user=user,
        used_at__isnull=True,
    ).count()
