from django import forms
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import DashboardAnnouncement


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = DashboardAnnouncement
        fields = ["kind", "text", "expires_at"]

    def clean_expires_at(self):
        value = self.cleaned_data["expires_at"]
        if value is not None and value <= timezone.now():
            raise forms.ValidationError(
                "Das Ablaufdatum muss in der Zukunft liegen."
            )
        return value


@login_required
@require_POST
def create_announcement(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden()
    form = AnnouncementForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=400)
    form.save()
    return JsonResponse({"ok": True}, status=201)


@login_required
@require_POST
def delete_announcement(request, pk):
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden()
    get_object_or_404(DashboardAnnouncement, pk=pk).delete()
    return JsonResponse({"ok": True})
