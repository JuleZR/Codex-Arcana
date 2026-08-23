"""Daemonic power definitions, semantic effects, and character ownership."""

from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from ..constants import (
    MODIFIER_OPERATOR_CHOICES,
    MODIFIER_VISIBILITY_CHOICES,
    STACK_BEHAVIOR_CHOICES,
)
from .core import Race
from .creatures import CREATURE_TARGET_DOMAIN_CHOICES


DAEMONIC_POWER_TARGET_DOMAIN_CHOICES = CREATURE_TARGET_DOMAIN_CHOICES + (
    ("daemonic_power", "daemonic_power"),
)


class DaemonicPowerTier(models.Model):
    """Ordered catalogue tier used to group daemonic powers."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    sort_number = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["sort_number", "name", "id"]
        verbose_name = "Daemonic power tier"
        verbose_name_plural = "Daemonic power tiers"

    def __str__(self) -> str:
        return self.name


class DaemonicPower(models.Model):
    """Reusable daemonic power with a description and associated weakness."""

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=150, unique=True)
    tier = models.ForeignKey(
        DaemonicPowerTier,
        on_delete=models.PROTECT,
        related_name="powers",
    )
    description = models.TextField(blank=True, default="")
    weakness_description = models.TextField(
        "Associated weakness",
        blank=True,
        default="",
    )

    class Meta:
        ordering = ["tier__sort_number", "tier__name", "name", "id"]
        verbose_name = "Daemonic power"
        verbose_name_plural = "Daemonic powers"

    def __str__(self) -> str:
        return f"{self.name} ({self.tier.name})"


class CreatureDaemonicPower(models.Model):
    """A daemonic power assigned to a base creature, optionally at a level."""

    creature = models.ForeignKey(
        "charsheet.Creature",
        on_delete=models.CASCADE,
        related_name="daemonic_power_values",
    )
    power = models.ForeignKey(
        DaemonicPower,
        db_column="daemonicpower_id",
        on_delete=models.CASCADE,
        related_name="base_creature_ownerships",
    )
    level = models.PositiveIntegerField("Level", blank=True, null=True)

    class Meta:
        db_table = "charsheet_creature_daemonic_powers"
        ordering = [
            "power__tier__sort_number",
            "power__tier__name",
            "power__name",
            "id",
        ]
        unique_together = (("creature", "power"),)
        verbose_name = "Creature daemonic power"
        verbose_name_plural = "Creature daemonic powers"

    def __str__(self) -> str:
        level_suffix = f" level {self.level}" if self.level is not None else ""
        return f"{self.creature}: {self.power}{level_suffix}"


class DaemonicPowerSemanticEffect(models.Model):
    """Semantic effect contributed by a daemonic power to either rules engine."""

    class ApplicationScope(models.TextChoices):
        CHARACTER = "character", "Character"
        CREATURE = "creature", "Creature"
        BOTH = "both", "Character and creature"

    power = models.ForeignKey(
        DaemonicPower,
        on_delete=models.CASCADE,
        related_name="semantic_effects",
    )
    application_scope = models.CharField(
        "Application scope",
        max_length=20,
        choices=ApplicationScope.choices,
        default=ApplicationScope.BOTH,
    )
    sort_order = models.PositiveIntegerField(default=0)
    target_skills = models.ManyToManyField(
        "charsheet.Skill",
        blank=True,
        related_name="daemonic_power_semantic_effects",
        help_text="Optional concrete skill targets.",
    )
    target_domain = models.CharField(
        max_length=40,
        choices=DAEMONIC_POWER_TARGET_DOMAIN_CHOICES,
        default="rule_flag",
    )
    target_key = models.CharField(max_length=120, blank=True, default="")
    operator = models.CharField(
        max_length=40,
        choices=MODIFIER_OPERATOR_CHOICES,
        default="flat_add",
    )
    mode = models.CharField(max_length=20, default="flat")
    value = models.CharField(max_length=200, blank=True, default="")
    value_min = models.IntegerField(null=True, blank=True)
    value_max = models.IntegerField(null=True, blank=True)
    formula = models.CharField(max_length=200, blank=True, default="")
    scaling = models.JSONField(default=dict, blank=True)
    stack_behavior = models.CharField(
        max_length=40,
        choices=STACK_BEHAVIOR_CHOICES,
        default="stack",
    )
    condition_set = models.JSONField(default=dict, blank=True)
    condition_races = models.ManyToManyField(
        Race,
        blank=True,
        related_name="daemonic_power_semantic_effect_conditions",
        help_text="Optional race condition. Leave empty to apply to every race.",
    )
    condition_schools = models.ManyToManyField(
        "charsheet.School",
        blank=True,
        related_name="+",
        help_text="Optional school condition. Leave empty to apply to every school.",
    )
    active_flag = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)
    condition_text = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    rules_text = models.TextField(blank=True, default="")
    visibility = models.CharField(
        max_length=20,
        choices=MODIFIER_VISIBILITY_CHOICES,
        default="public",
    )
    hidden = models.BooleanField(default=False)
    sheet_relevant = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["power", "sort_order", "id"]
        verbose_name = "Daemonic power semantic effect"
        verbose_name_plural = "Daemonic power semantic effects"

    def __str__(self) -> str:
        return f"{self.power.name}: {self.target_domain}/{self.target_key} ({self.operator})"

    @staticmethod
    def _coerce_scalar(raw_value):
        text = str(raw_value or "").strip()
        if text == "":
            return None
        lowered = text.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered == "null":
            return None
        try:
            return json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        try:
            return int(text)
        except (TypeError, ValueError):
            pass
        try:
            return float(text)
        except (TypeError, ValueError):
            pass
        return text

    def clean(self):
        super().clean()
        for field_name in ("scaling", "condition_set", "metadata"):
            if not isinstance(getattr(self, field_name), dict):
                raise ValidationError({field_name: f"{field_name} must be a JSON object."})
        if (
            self.application_scope in {
                self.ApplicationScope.CHARACTER,
                self.ApplicationScope.BOTH,
            }
            and self.target_domain.startswith("creature_")
            and self.target_domain != "creature_card"
        ):
            raise ValidationError(
                {
                    "target_domain": (
                        "Creature-only targets require the Creature application scope."
                    )
                }
            )
        if (
            self.target_domain == "daemonic_power"
            and not DaemonicPower.objects.filter(slug=self.target_key).exists()
        ):
            raise ValidationError(
                {
                    "target_key": (
                        "Daemonic-power effects require the slug of an existing "
                        "daemonic power."
                    )
                }
            )

    def to_modifier(self):
        """Materialize the effect for the character ModifierEngine."""
        from ..modifiers.definitions import (
            AttributeCapModifier,
            AttributeModifier,
            BaseModifier,
            CombatModifier,
            ConditionSet,
            DerivedStatModifier,
            EconomyModifier,
            LanguageModifier,
            MovementModifier,
            PerceptionModifier,
            ProficiencyGroupModifier,
            ResourceModifier,
            ResistanceModifier,
            RuleFlagModifier,
            SkillModifier,
            SocialModifier,
            TraitModifier,
        )

        modifier_map = {
            "skill": SkillModifier,
            "skill_category": SkillModifier,
            "skill_rank": SkillModifier,
            "skill_rank_cap": SkillModifier,
            "trait": TraitModifier,
            "language": LanguageModifier,
            "proficiency_group": ProficiencyGroupModifier,
            "attribute": AttributeModifier,
            "attribute_cap": AttributeCapModifier,
            "derived_stat": DerivedStatModifier,
            "resource": ResourceModifier,
            "resistance": ResistanceModifier,
            "movement": MovementModifier,
            "combat": CombatModifier,
            "perception": PerceptionModifier,
            "economy": EconomyModifier,
            "social": SocialModifier,
            "rule_flag": RuleFlagModifier,
        }
        modifier_cls = modifier_map.get(self.target_domain, BaseModifier)
        metadata = dict(self.metadata or {})
        if self.pk:
            metadata["semantic_effect_key"] = f"daemonic_power_effect:{self.pk}"
            metadata["semantic_effect_label"] = self.power.name
            condition_race_ids = list(self.condition_races.order_by("id").values_list("id", flat=True))
            if condition_race_ids:
                metadata["condition_race_ids"] = condition_race_ids
            condition_school_ids = list(
                self.condition_schools.order_by("id").values_list("id", flat=True)
            )
            if condition_school_ids:
                metadata["condition_school_ids"] = condition_school_ids
        condition_text = " ".join(str(self.condition_text or "").split())
        if condition_text:
            metadata["condition_text"] = condition_text
        if self.pk:
            skill_slugs = list(
                self.target_skills.order_by("slug").values_list("slug", flat=True)
            )
            if skill_slugs:
                metadata["target_skill_slugs"] = skill_slugs
        return modifier_cls(
            source_type="daemonic_power",
            source_id=str(self.power_id),
            target_domain=self.target_domain,
            target_key=self.target_key,
            mode=self.mode,
            value=self._coerce_scalar(self.value),
            value_min=self.value_min,
            value_max=self.value_max,
            formula=self.formula,
            scaling=dict(self.scaling or {}),
            operator=self.operator,
            stack_behavior=self.stack_behavior,
            condition_set=ConditionSet(**dict(self.condition_set or {})),
            active_flag=bool(self.active_flag),
            priority=int(self.priority),
            notes=self.notes,
            rules_text=self.rules_text,
            visibility=self.visibility,
            hidden=bool(self.hidden),
            sheet_relevant=bool(self.sheet_relevant),
            metadata=metadata,
        )


class CharacterDaemonicPower(models.Model):
    """One daemonic power selected for a character through a granting technique."""

    character = models.ForeignKey(
        "charsheet.Character",
        on_delete=models.CASCADE,
        related_name="daemonic_power_ownerships",
    )
    power = models.ForeignKey(
        DaemonicPower,
        on_delete=models.PROTECT,
        related_name="character_ownerships",
    )
    granting_technique = models.ForeignKey(
        "charsheet.Technique",
        on_delete=models.CASCADE,
        related_name="granted_character_daemonic_powers",
    )

    class Meta:
        ordering = [
            "character",
            "power__tier__sort_number",
            "power__tier__name",
            "power__name",
            "id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "power"],
                name="uniq_character_daemonic_power",
            ),
            models.UniqueConstraint(
                fields=["character", "granting_technique"],
                name="uniq_character_daemonic_power_grant",
            ),
        ]
        verbose_name = "Character daemonic power"
        verbose_name_plural = "Character daemonic powers"

    def __str__(self) -> str:
        return f"{self.character}: {self.power} via {self.granting_technique}"

    def clean(self):
        super().clean()
        if not self.granting_technique_id or not self.power_id:
            return
        required_tier_id = self.granting_technique.granted_daemonic_power_tier_id
        if required_tier_id is None:
            raise ValidationError(
                {"granting_technique": "This technique does not grant a daemonic power."}
            )
        if self.power.tier_id != required_tier_id:
            raise ValidationError(
                {"power": "The selected power must belong to the technique's exact grant tier."}
            )


class CharacterCreatureDaemonicPower(models.Model):
    """Additional daemonic power selected through creature training."""

    creature = models.ForeignKey(
        "charsheet.CharacterCreature",
        on_delete=models.CASCADE,
        related_name="daemonic_power_additions",
    )
    power = models.ForeignKey(
        DaemonicPower,
        on_delete=models.PROTECT,
        related_name="character_creature_ownerships",
    )

    class Meta:
        ordering = [
            "creature",
            "power__tier__sort_number",
            "power__tier__name",
            "power__name",
            "id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["creature", "power"],
                name="uniq_character_creature_daemonic_power",
            )
        ]
        verbose_name = "Character creature daemonic power"
        verbose_name_plural = "Character creature daemonic powers"

    def __str__(self) -> str:
        return f"{self.creature}: {self.power}"

    def clean(self):
        super().clean()
        if (
            self.creature_id
            and self.power_id
            and self.creature.creature_id
            and self.creature.creature.daemonic_powers.filter(pk=self.power_id).exists()
        ):
            raise ValidationError(
                {"power": "A base power cannot be added again through creature training."}
            )


@receiver(post_delete, sender="charsheet.CharacterTechnique")
def remove_daemonic_power_after_explicit_technique_loss(
    sender,
    instance,
    **kwargs,
):
    """Remove a grant choice when its explicit learned-technique row is deleted."""
    CharacterDaemonicPower.objects.filter(
        character_id=instance.character_id,
        granting_technique_id=instance.technique_id,
    ).delete()
