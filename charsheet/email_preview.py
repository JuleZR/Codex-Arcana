"""Local-only previews using fixed, deliberately invalid example links."""

from ipaddress import ip_address

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe


EMAIL_TEMPLATES = {
    "verification": "registration/email_verification_email",
    "password-reset": "registration/codex_password_reset_email",
}


@never_cache
@require_safe
def email_preview(request, email_type="verification"):
    """Render the real templates without users, token creation or delivery."""
    try:
        local_request = ip_address(
            request.META.get("REMOTE_ADDR", "")
        ).is_loopback
    except ValueError:
        local_request = False
    if (
        not settings.DEBUG
        or not local_request
        or request.get_host().split(":")[0] not in {"localhost", "127.0.0.1"}
    ):
        raise Http404
    template = EMAIL_TEMPLATES.get(email_type)
    if template is None:
        raise Http404

    context = {
        "email_logo_url": request.build_absolute_uri(
            static("img/codexarcana.png")
        ),
        "verification_url": (
            "https://example.invalid/email-verification/preview-only/"
        ),
        "timeout_seconds": settings.EMAIL_VERIFICATION_TIMEOUT,
        "protocol": "https",
        "domain": "example.invalid",
        "uid": "preview",
        "token": "preview-only",
    }
    output_format = request.GET.get("format", "preview")
    if output_format in {"html", "text"}:
        extension = "html" if output_format == "html" else "txt"
        content_type = (
            "text/html" if output_format == "html" else "text/plain"
        )
        return HttpResponse(
            render_to_string(f"{template}.{extension}", context),
            content_type=f"{content_type}; charset=utf-8",
        )
    if output_format != "preview":
        raise Http404
    return render(request, "registration/email_preview.html", {
        "email_type": email_type,
    })
