"""Central authentication throttling and optional Turnstile validation."""

from dataclasses import dataclass
from datetime import timedelta
import ipaddress
import logging

import requests
from axes.backends import AxesStandaloneBackend
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db import transaction
from django.dispatch import receiver
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import AccountSecurityEvent, AuthenticationThrottle


logger = logging.getLogger("django.security.auth")


def _device_summary(user_agent: str) -> str:
    """Return a deliberately coarse browser and operating-system summary."""

    value = (user_agent or "").strip()
    if not value:
        return ""

    browser = "Unknown browser"
    for marker, label in (
        ("Edg/", "Edge"),
        ("Firefox/", "Firefox"),
        ("Chrome/", "Chrome"),
        ("Safari/", "Safari"),
    ):
        if marker in value:
            browser = label
            break

    operating_system = "Unknown device"
    for marker, label in (
        ("Windows", "Windows"),
        ("Android", "Android"),
        ("iPhone", "iPhone"),
        ("iPad", "iPad"),
        ("Mac OS X", "macOS"),
        ("Linux", "Linux"),
    ):
        if marker in value:
            operating_system = label
            break
    return f"{browser} on {operating_system}"


def _request_ip(request):
    if request is None:
        return None
    value = get_client_ip(request)
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def _safe_event_metadata(metadata):
    """Allow only small, non-secret values used by event descriptions."""

    metadata = metadata or {}
    safe = {}
    label = str(metadata.get("label", "")).strip()
    if label:
        safe["label"] = label[:120]
    session_count = metadata.get("session_count")
    if isinstance(session_count, int) and session_count >= 0:
        safe["session_count"] = session_count
    return safe


def purge_expired_security_events(*, now=None):
    """Delete audit entries beyond the configured retention period."""

    cutoff = (now or timezone.now()) - timedelta(
        days=settings.ACCOUNT_SECURITY_ACTIVITY_RETENTION_DAYS
    )
    expired_events = AccountSecurityEvent.objects.filter(
        created_at__lt=cutoff
    )
    return expired_events.delete()[0]


def record_security_event(user, event_type, *, request=None, metadata=None):
    """Record one successful or relevant failed account-security action."""

    if user is None or not getattr(user, "pk", None):
        return None
    event = AccountSecurityEvent.objects.create(
        user=user,
        event_type=event_type,
        source_ip=_request_ip(request),
        device=_device_summary(
            request.META.get("HTTP_USER_AGENT", "") if request else ""
        ),
        metadata=_safe_event_metadata(metadata),
    )
    purge_expired_security_events()
    return event


@receiver(user_logged_in)
def record_successful_login(sender, request, user, **kwargs):
    record_security_event(
        user,
        AccountSecurityEvent.EventType.LOGIN_SUCCEEDED,
        request=request,
    )


@receiver(user_login_failed)
def record_failed_login(sender, credentials, request, **kwargs):
    if request is None:
        return
    user_model = get_user_model()
    username_field = user_model.USERNAME_FIELD
    account_reference = credentials.get(username_field)
    if not account_reference:
        return
    user = user_model._default_manager.filter(
        **{username_field: account_reference}
    ).first()
    if user is not None:
        record_security_event(
            user,
            AccountSecurityEvent.EventType.LOGIN_FAILED,
            request=request,
        )


class RequestAwareAxesBackend(AxesStandaloneBackend):
    """Protect HTTP logins without breaking trusted internal auth calls."""

    def authenticate(self, request, **credentials):
        if request is None:
            return None
        return super().authenticate(request, **credentials)


@dataclass(frozen=True)
class RateLimitResult:
    limited: bool
    retry_after: int = 0


def get_client_ip(request) -> str:
    """Return the connection IP without trusting forwarding headers."""

    return (request.META.get("REMOTE_ADDR") or "unknown").strip()


def _bucket_digest(category: str, kind: str, value: str) -> str:
    normalized = value.strip().casefold()
    return salted_hmac(
        "charsheet.authentication-throttle",
        f"{category}:{kind}:{normalized}",
        algorithm="sha256",
    ).hexdigest()


def _consume_bucket(category: str, key_digest: str) -> RateLimitResult:
    config = settings.AUTH_RATE_LIMITS[category]
    now = timezone.now()
    window = timedelta(seconds=config["window"])
    cooldown = timedelta(seconds=config["cooldown"])

    with transaction.atomic():
        bucket, _ = (
            AuthenticationThrottle.objects.select_for_update().get_or_create(
                category=category,
                key_digest=key_digest,
                defaults={"window_started_at": now},
            )
        )
        if bucket.blocked_until and bucket.blocked_until > now:
            retry_after = max(
                1,
                int((bucket.blocked_until - now).total_seconds()),
            )
            return RateLimitResult(True, retry_after)

        if bucket.blocked_until or now - bucket.window_started_at >= window:
            bucket.attempts = 0
            bucket.window_started_at = now
            bucket.blocked_until = None

        if bucket.attempts >= config["limit"]:
            bucket.blocked_until = now + cooldown
            bucket.save(update_fields=["blocked_until", "updated_at"])
            return RateLimitResult(True, config["cooldown"])

        bucket.attempts += 1
        bucket.save(
            update_fields=[
                "attempts",
                "window_started_at",
                "blocked_until",
                "updated_at",
            ]
        )
    return RateLimitResult(False)


def consume_auth_rate_limit(
    request,
    category: str,
    *,
    account_reference: str = "",
) -> RateLimitResult:
    """Consume per-IP and optional per-account buckets for one auth action."""

    if category not in settings.AUTH_RATE_LIMITS:
        raise ValueError(
            f"Unknown authentication rate-limit category: {category}"
        )

    source_ip = get_client_ip(request)
    buckets = [("ip", source_ip)]
    if account_reference:
        buckets.append(("account", account_reference))

    for kind, value in buckets:
        result = _consume_bucket(
            category,
            _bucket_digest(category, kind, value),
        )
        if result.limited:
            logger.warning(
                "authentication_rate_limit_triggered category=%s "
                "source_ip=%s bucket=%s",
                category,
                source_ip,
                kind,
            )
            return result
    return RateLimitResult(False)


def clear_auth_rate_limit(
    request,
    category: str,
    *,
    account_reference: str = "",
) -> None:
    """Clear relevant failure buckets after successful authentication."""

    bucket_digests = [
        _bucket_digest(category, "ip", get_client_ip(request)),
    ]
    if account_reference:
        bucket_digests.append(
            _bucket_digest(category, "account", account_reference)
        )
    AuthenticationThrottle.objects.filter(
        category=category,
        key_digest__in=bucket_digests,
    ).delete()


def turnstile_required(category: str) -> bool:
    return (
        settings.AUTH_TURNSTILE_ENABLED
        and category in settings.AUTH_TURNSTILE_CATEGORIES
    )


def verify_turnstile(request, category: str) -> bool:
    """Validate a Turnstile response server-side without logging its token."""

    if not turnstile_required(category):
        return True
    if not (
        settings.AUTH_TURNSTILE_SITE_KEY
        and settings.AUTH_TURNSTILE_SECRET_KEY
    ):
        logger.error(
            "authentication_turnstile_misconfigured category=%s",
            category,
        )
        return False

    token = (request.POST.get("cf-turnstile-response") or "").strip()
    if not token or len(token) > 2048:
        return False

    try:
        response = requests.post(
            settings.AUTH_TURNSTILE_VERIFY_URL,
            data={
                "secret": settings.AUTH_TURNSTILE_SECRET_KEY,
                "response": token,
                "remoteip": get_client_ip(request),
            },
            timeout=settings.AUTH_TURNSTILE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError):
        logger.warning(
            "authentication_turnstile_unavailable category=%s source_ip=%s",
            category,
            get_client_ip(request),
        )
        return False

    return result.get("success") is True
