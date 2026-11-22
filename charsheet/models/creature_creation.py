"""Creation metadata attached to the existing creature and trait models."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class CreatureCategoryRule(models.Model):
    category = models.CharField(
        "Kreaturenkategorie", max_length=8, unique=True
    )
    grants_natural_survival = models.BooleanField(
        "Natürliche Überlebensfertigkeit (Gesamtwert 6)", default=False
    )

    class Meta:
        ordering = ["category"]
        verbose_name = "Kreaturenkategorie: Erschaffungsregel"
        verbose_name_plural = "Kreaturenkategorien: Erschaffungsregeln"

    def __str__(self):
        from charsheet.engine.creature_power import CATEGORIES

        return CATEGORIES.get(self.category, (self.category,))[0]

    def clean(self):
        from charsheet.engine.creature_power import CATEGORIES

        super().clean()
        if self.category not in CATEGORIES:
            raise ValidationError(
                {"category": "Unbekannte Kreaturenkategorie."}
            )


class CreaturePowerRule(models.Model):
    """Database-defined MP costs; training points remain separate."""

    name = models.CharField(max_length=150, unique=True)
    key = models.SlugField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    categories = models.JSONField(default=list, blank=True)
    requirements = models.JSONField(default=dict, blank=True)
    cost_kind = models.CharField(
        max_length=12,
        choices=[
            ("fixed", "Fest"),
            ("level", "Stufenabhängig"),
            ("composite", "Zusammengesetzt"),
        ],
        default="fixed",
    )
    formula = models.CharField(max_length=1000)
    parameters = models.JSONField(default=dict, blank=True)
    effects = models.JSONField(default=dict, blank=True)
    official = models.BooleanField(default=False)
    source = models.CharField(max_length=150, blank=True)
    trait = models.OneToOneField(
        "charsheet.CreatureTraitDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="power_rule",
    )
    special_skill = models.OneToOneField(
        "charsheet.CreatureSpecialSkill",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="power_rule",
    )
    daemonic_power = models.OneToOneField(
        "charsheet.DaemonicPower",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="creature_power_rule",
    )
    vampire_power = models.OneToOneField(
        "charsheet.VampirePower",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="creature_power_rule",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        from charsheet.engine.creature_power import formula_value

        super().clean()
        try:
            formula_value(
                self.formula,
                {
                    key: spec.get("min", 1)
                    for key, spec in self.parameters.items()
                },
            )
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValidationError({"formula": str(exc)}) from exc


class CreatureCreation(models.Model):
    """Working copy and rule-only information for one existing Creature."""

    creature = models.OneToOneField(
        "charsheet.Creature",
        on_delete=models.CASCADE,
        related_name="creation",
        null=True,
        blank=True,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="creature_creations",
    )
    released = models.BooleanField(default=False)
    rules = models.JSONField(default=dict, blank=True)
    draft = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.creature)
