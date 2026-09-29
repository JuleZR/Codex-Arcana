"""Server-side WebAuthn ceremonies for optional passkey authentication."""

import json

from django.conf import settings
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)


def user_handle(user):
    """Return a stable, non-personal WebAuthn user handle."""
    return f"codex-arcana-user:{user.pk}".encode("ascii")


def user_verification_requirement():
    configured = str(settings.WEBAUTHN_USER_VERIFICATION).lower()
    try:
        return UserVerificationRequirement(configured)
    except ValueError:
        return UserVerificationRequirement.REQUIRED


def registration_options(user, credentials):
    options = generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=user_handle(user),
        user_name=user.get_username(),
        user_display_name=user.get_full_name() or user.get_username(),
        timeout=settings.WEBAUTHN_CHALLENGE_TIMEOUT_SECONDS * 1000,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=user_verification_requirement(),
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=bytes(credential.credential_id))
            for credential in credentials
        ],
    )
    return options, json.loads(options_to_json(options))


def verify_registration(credential, challenge):
    return verify_registration_response(
        credential=credential,
        expected_challenge=challenge,
        expected_rp_id=settings.WEBAUTHN_RP_ID,
        expected_origin=settings.WEBAUTHN_ALLOWED_ORIGINS,
        require_user_verification=(
            user_verification_requirement()
            == UserVerificationRequirement.REQUIRED
        ),
    )


def authentication_options():
    options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        timeout=settings.WEBAUTHN_CHALLENGE_TIMEOUT_SECONDS * 1000,
        allow_credentials=[],
        user_verification=user_verification_requirement(),
    )
    return options, json.loads(options_to_json(options))


def verify_authentication(credential, challenge, passkey):
    return verify_authentication_response(
        credential=credential,
        expected_challenge=challenge,
        expected_rp_id=settings.WEBAUTHN_RP_ID,
        expected_origin=settings.WEBAUTHN_ALLOWED_ORIGINS,
        credential_public_key=bytes(passkey.public_key),
        credential_current_sign_count=passkey.sign_count,
        require_user_verification=(
            user_verification_requirement()
            == UserVerificationRequirement.REQUIRED
        ),
    )
