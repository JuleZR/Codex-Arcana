"""Private snapshots of character creation input, without character links."""

from django.conf import settings
from django.db import models


class CharacterCreationTemplate(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="character_creation_templates",
    )
    name = models.CharField(max_length=100)
    race = models.ForeignKey("Race", on_delete=models.CASCADE)
    state = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name
