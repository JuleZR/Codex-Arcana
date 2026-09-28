from dataclasses import dataclass

from django.conf import settings
from django.contrib.sessions.models import Session
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .auth_security import record_security_event
from .models import AccountSecurityEvent


SESSION_REFERENCE_SALT = "charsheet.active-session"


@dataclass(frozen=True)
class ActiveSession:
    reference: str
    expire_date: object
    is_current: bool


def _session_reference(session_key):
    return salted_hmac(SESSION_REFERENCE_SALT, session_key).hexdigest()


def _user_session_rows(user):
    user_id = str(user.pk)
    sessions = Session.objects.filter(expire_date__gt=timezone.now()).order_by(
        "expire_date",
        "session_key",
    )
    for session in sessions.iterator():
        if str(session.get_decoded().get("_auth_user_id")) == user_id:
            yield session


def active_sessions_for_user(user, current_session_key=None):
    return [
        ActiveSession(
            reference=_session_reference(session.session_key),
            expire_date=session.expire_date,
            is_current=session.session_key == current_session_key,
        )
        for session in _user_session_rows(user)
    ]


def terminate_user_sessions(
    user,
    *,
    reference=None,
    exclude_session_key=None,
):
    deleted_count = 0
    for session in _user_session_rows(user):
        if session.session_key == exclude_session_key:
            continue
        if reference is not None and not constant_time_compare(
            _session_reference(session.session_key),
            reference,
        ):
            continue
        session.delete()
        deleted_count += 1
        if reference is not None:
            break
    return deleted_count


@receiver(pre_save, sender=settings.AUTH_USER_MODEL)
def remember_previous_account_state(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_is_active = None
        return
    instance._previous_is_active = sender._default_manager.filter(
        pk=instance.pk
    ).values_list("is_active", flat=True).first()


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def handle_account_state_change(sender, instance, created, **kwargs):
    if not instance.is_active:
        terminate_user_sessions(instance)
    previous = getattr(instance, "_previous_is_active", None)
    if created or previous is None or previous == instance.is_active:
        return
    event_type = (
        AccountSecurityEvent.EventType.ACCOUNT_REACTIVATED
        if instance.is_active
        else AccountSecurityEvent.EventType.ACCOUNT_DEACTIVATED
    )
    record_security_event(instance, event_type)


@receiver(pre_delete, sender=settings.AUTH_USER_MODEL)
def terminate_sessions_for_deleted_user(sender, instance, **kwargs):
    terminate_user_sessions(instance)
