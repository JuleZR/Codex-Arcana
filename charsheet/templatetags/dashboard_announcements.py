from django import template

from charsheet.models import DashboardAnnouncement


register = template.Library()


@register.inclusion_tag(
    "charsheet/partials/_dashboard_announcements.html", takes_context=True,
)
def dashboard_announcements(context):
    request = context["request"]
    return {
        "announcements": DashboardAnnouncement.active(),
        "can_manage": request.user.is_staff or request.user.is_superuser,
        "csrf_token": context["csrf_token"],
    }
