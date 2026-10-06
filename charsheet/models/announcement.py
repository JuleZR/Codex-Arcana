from django.db import models
from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone


class DashboardAnnouncement(models.Model):
    class Kind(models.TextChoices):
        UPDATE = "update", "Update"
        WARNING = "warning", "Warnung"
        CRITICAL = "critical", "Kritisch"

    kind = models.CharField(max_length=8, choices=Kind.choices)
    text = models.TextField(max_length=20000)
    created_at = models.DateTimeField(auto_now_add=True)
    sort_order = models.IntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["sort_order", "-created_at", "-pk"]

    @classmethod
    def active(cls):
        return cls.objects.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).order_by(
            Case(
                When(sort_order=-1, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
            Case(
                When(sort_order=-1, then=Value(0)),
                default=models.F("sort_order"),
                output_field=IntegerField(),
            ),
            Case(
                When(sort_order=-1, kind=cls.Kind.CRITICAL, then=Value(0)),
                When(sort_order=-1, kind=cls.Kind.WARNING, then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            ),
            "-created_at",
            "-pk",
        )
