"""Shared vampire traits, semantic effects, and domain-specific ownership."""

from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.db import models

from ..constants import (
    MODIFIER_OPERATOR_CHOICES,
    MODIFIER_VISIBILITY_CHOICES,
    STACK_BEHAVIOR_CHOICES,
)
from .creatures import CREATURE_TARGET_DOMAIN_CHOICES


VAMPIRE_TRAIT_TARGET_DOMAIN_CHOICES = CREATURE_TARGET_DOMAIN_CHOICES


class VampireTrait(models.Model):
    """One fundamental vampiric advantage or disadvantage."""

    class TraitType(models.TextChoices):
        ADVANTAGE = "advantage", "Advantage"
        DISADVANTAGE = "disadvantage", "Disadvantage"

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=150, unique=True)
    trait_type = models.CharField(max_length=20, choices=TraitType.choices)
    description = models.TextField(blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name", "id"]
        verbose_name = "Vampire trait"
        verbose_name_plural = "Vampire traits"

    def __str__(self) -> str:
        return self.name


class VampirePower(models.Model):
    """One learnable vampire power with a fixed associated disadvantage."""

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=150, unique=True)
    description = models.TextField(blank=True, default="")
    weakness = models.TextField()
    blood_cost = models.PositiveSmallIntegerField(blank=True, null=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name", "id"]
        verbose_name = "Vampire power"
        verbose_name_plural = "Vampire powers"

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        if not str(self.weakness or "").strip():
            raise ValidationError({"weakness": "Every vampire power requires weakness text."})


class VampireTraitSemanticEffect(models.Model):
    """Passive semantic effect contributed by one vampire trait."""

    class ApplicationScope(models.TextChoices):
        CHARACTER = "character", "Character"
        CREATURE = "creature", "Creature"
        BOTH = "both", "Character and creature"

    class PowerComponent(models.TextChoices):
        POWER = "power", "Power"
        WEAKNESS = "weakness", "Weakness"

    trait = models.ForeignKey(
        VampireTrait,
        on_delete=models.CASCADE,
        related_name="semantic_effects",
        blank=True,
        null=True,
    )
    power = models.ForeignKey(
        VampirePower,
        on_delete=models.CASCADE,
        related_name="semantic_effects",
        blank=True,
        null=True,
    )
    application_scope = models.CharField(
        max_length=20,
        choices=ApplicationScope.choices,
        default=ApplicationScope.BOTH,
    )
    power_component = models.CharField(
        max_length=20,
        choices=PowerComponent.choices,
        default=PowerComponent.POWER,
        help_text="For power effects: whether the effect belongs to the power or its weakness.",
    )
    sort_order = models.PositiveIntegerField(default=0)
    target_skills = models.ManyToManyField(
        "charsheet.Skill",
        blank=True,
        related_name="vampire_trait_semantic_effects",
    )
    target_schools = models.ManyToManyField(
        "charsheet.School",
        blank=True,
        related_name="vampire_disallow_semantic_effects",
    )
    target_domain = models.CharField(
        max_length=40,
        choices=VAMPIRE_TRAIT_TARGET_DOMAIN_CHOICES,
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
        ordering = ["trait", "sort_order", "id"]
        verbose_name = "Vampire trait semantic effect"
        verbose_name_plural = "Vampire trait semantic effects"

    def __str__(self) -> str:
        definition = self.definition
        name = definition.name if definition is not None else "Unassigned vampire effect"
        return f"{name}: {self.target_domain}/{self.target_key} ({self.operator})"

    @property
    def definition(self):
        return self.power or self.trait

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
            return text

    def clean(self):
        super().clean()
        if self.trait_id and self.power_id:
            raise ValidationError("A vampire semantic effect cannot belong to both a trait and a power.")
        if self.trait_id and self.power_component == self.PowerComponent.WEAKNESS:
            raise ValidationError({"power_component": "Only power effects can belong to a weakness."})
        for field_name in ("scaling", "condition_set", "metadata"):
            if not isinstance(getattr(self, field_name), dict):
                raise ValidationError({field_name: f"{field_name} must be a JSON object."})
        if (
            self.application_scope in {self.ApplicationScope.CHARACTER, self.ApplicationScope.BOTH}
            and self.target_domain.startswith("creature_")
        ):
            raise ValidationError(
                {"target_domain": "Creature targets require the creature application scope."}
            )

    def to_modifier(self, *, rank: int = 1, age_cycle: int = 1):
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
            "capability": BaseModifier,
        }
        definition = self.definition
        if definition is None:
            raise ValidationError("Vampire semantic effect has no trait or power.")
        source_kind = "vampire_power" if self.power_id else "vampire_trait"
        metadata = {
            **dict(self.metadata or {}),
            f"{source_kind}_slug": definition.slug,
            "vampire_trait_rank": max(1, int(rank or 1)),
            "vampire_age_cycle": max(1, int(age_cycle or 1)),
        }
        condition_text = " ".join(str(self.condition_text or "").split())
        if condition_text:
            metadata["condition_text"] = condition_text
        if self.pk:
            skill_slugs = list(self.target_skills.order_by("slug").values_list("slug", flat=True))
            if skill_slugs:
                metadata["target_skill_slugs"] = skill_slugs
        scaling = dict(self.scaling or {})
        scaling["_vampire_trait_rank"] = max(1, int(rank or 1))
        scaling["_vampire_age_cycle"] = max(1, int(age_cycle or 1))
        modifier_cls = modifier_map.get(self.target_domain, BaseModifier)
        return modifier_cls(
            source_type=source_kind,
            source_id=str(definition.id),
            target_domain=self.target_domain,
            target_key=self.target_key,
            mode=self.mode,
            value=self._coerce_scalar(self.value),
            value_min=self.value_min,
            value_max=self.value_max,
            formula=self.formula,
            scaling=scaling,
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


class CharacterVampireTrait(models.Model):
    character = models.ForeignKey(
        "charsheet.Character",
        on_delete=models.CASCADE,
        related_name="vampire_trait_ownerships",
    )
    trait = models.ForeignKey(
        VampireTrait,
        on_delete=models.PROTECT,
        related_name="character_ownerships",
    )

    class Meta:
        ordering = ["character", "trait__sort_order", "trait__name", "id"]
        verbose_name = "Character vampire trait"
        verbose_name_plural = "Character vampire traits"
        constraints = [
            models.UniqueConstraint(fields=["character", "trait"], name="uniq_character_vampire_trait")
        ]

    def clean(self):
        super().clean()
        if self.character_id and not self.character.is_vampire:
            raise ValidationError({"character": "Vampire traits require the Vampirism acquisition trait."})

    def __str__(self) -> str:
        return f"{self.character}: {self.trait}"


class CharacterVampirePower(models.Model):
    character = models.ForeignKey(
        "charsheet.Character",
        on_delete=models.CASCADE,
        related_name="vampire_power_ownerships",
    )
    power = models.ForeignKey(
        VampirePower,
        on_delete=models.PROTECT,
        related_name="character_ownerships",
    )
    purchased_without_weakness = models.BooleanField(default=False)
    weakness_bought_off = models.BooleanField(default=False)

    class Meta:
        ordering = ["character", "power__sort_order", "power__name", "id"]
        verbose_name = "Character vampire power"
        verbose_name_plural = "Character vampire powers"
        constraints = [
            models.UniqueConstraint(fields=["character", "power"], name="uniq_character_vampire_power")
        ]

    @property
    def weakness_is_active(self) -> bool:
        return not self.purchased_without_weakness and not self.weakness_bought_off

    def clean(self):
        super().clean()
        if self.character_id and not self.character.is_vampire:
            raise ValidationError({"character": "Vampire powers require the Vampirism acquisition trait."})

    def __str__(self) -> str:
        return f"{self.character}: {self.power}"


class CreatureVampireTrait(models.Model):
    creature = models.ForeignKey(
        "charsheet.Creature",
        on_delete=models.CASCADE,
        related_name="vampire_trait_defaults",
    )
    trait = models.ForeignKey(
        VampireTrait,
        on_delete=models.PROTECT,
        related_name="creature_defaults",
    )
    class Meta:
        ordering = ["creature", "trait__sort_order", "trait__name", "id"]
        verbose_name = "Creature vampire trait"
        verbose_name_plural = "Creature vampire traits"
        constraints = [
            models.UniqueConstraint(fields=["creature", "trait"], name="uniq_creature_vampire_trait")
        ]

    def __str__(self) -> str:
        return f"{self.creature}: {self.trait}"


class CreatureVampirePower(models.Model):
    creature = models.ForeignKey(
        "charsheet.Creature",
        on_delete=models.CASCADE,
        related_name="vampire_power_defaults",
    )
    power = models.ForeignKey(VampirePower, on_delete=models.PROTECT, related_name="creature_defaults")
    purchased_without_weakness = models.BooleanField(default=False)
    weakness_bought_off = models.BooleanField(default=False)

    class Meta:
        ordering = ["creature", "power__sort_order", "power__name", "id"]
        verbose_name = "Creature vampire power"
        verbose_name_plural = "Creature vampire powers"
        constraints = [
            models.UniqueConstraint(fields=["creature", "power"], name="uniq_creature_vampire_power")
        ]

    @property
    def weakness_is_active(self) -> bool:
        return not self.purchased_without_weakness and not self.weakness_bought_off

    def validation_warnings(self) -> list[str]:
        return []

    def __str__(self) -> str:
        return f"{self.creature}: {self.power}"


class VampireTraitOverrideMode(models.TextChoices):
    ADD = "add", "Add"
    REMOVE = "remove", "Remove"
    OVERRIDE = "override", "Override"


class CharacterCreatureVampireTrait(models.Model):
    creature = models.ForeignKey(
        "charsheet.CharacterCreature",
        on_delete=models.CASCADE,
        related_name="vampire_trait_overrides",
    )
    trait = models.ForeignKey(
        VampireTrait,
        on_delete=models.PROTECT,
        related_name="character_creature_overrides",
    )
    mode = models.CharField(max_length=12, choices=VampireTraitOverrideMode.choices, default=VampireTraitOverrideMode.ADD)

    class Meta:
        ordering = ["creature", "trait__sort_order", "trait__name", "id"]
        verbose_name = "Character creature vampire trait"
        verbose_name_plural = "Character creature vampire traits"
        constraints = [
            models.UniqueConstraint(fields=["creature", "trait"], name="uniq_character_creature_vampire_trait")
        ]

    def __str__(self) -> str:
        return f"{self.creature}: {self.mode} {self.trait}"


class CharacterCreatureVampirePower(models.Model):
    creature = models.ForeignKey(
        "charsheet.CharacterCreature",
        on_delete=models.CASCADE,
        related_name="vampire_power_overrides",
    )
    power = models.ForeignKey(
        VampirePower,
        on_delete=models.PROTECT,
        related_name="character_creature_overrides",
    )
    mode = models.CharField(max_length=12, choices=VampireTraitOverrideMode.choices, default=VampireTraitOverrideMode.ADD)
    purchased_without_weakness = models.BooleanField(blank=True, null=True)
    weakness_bought_off = models.BooleanField(blank=True, null=True)

    class Meta:
        ordering = ["creature", "power__sort_order", "power__name", "id"]
        verbose_name = "Character creature vampire power"
        verbose_name_plural = "Character creature vampire powers"
        constraints = [
            models.UniqueConstraint(fields=["creature", "power"], name="uniq_character_creature_vampire_power")
        ]

    def validation_warnings(self) -> list[str]:
        if self.mode == VampireTraitOverrideMode.REMOVE and (
            self.purchased_without_weakness is not None or self.weakness_bought_off is not None
        ):
            return ["A remove override ignores weakness values."]
        return []

    def __str__(self) -> str:
        return f"{self.creature}: {self.mode} {self.power}"


class GameGroupCreatureVampireTrait(models.Model):
    creature = models.ForeignKey(
        "charsheet.GameGroupCreature",
        on_delete=models.CASCADE,
        related_name="vampire_trait_overrides",
    )
    trait = models.ForeignKey(
        VampireTrait,
        on_delete=models.PROTECT,
        related_name="game_group_creature_overrides",
    )
    mode = models.CharField(max_length=12, choices=VampireTraitOverrideMode.choices, default=VampireTraitOverrideMode.ADD)

    class Meta:
        ordering = ["creature", "trait__sort_order", "trait__name", "id"]
        verbose_name = "Game group creature vampire trait"
        verbose_name_plural = "Game group creature vampire traits"
        constraints = [
            models.UniqueConstraint(fields=["creature", "trait"], name="uniq_group_creature_vampire_trait")
        ]

    def __str__(self) -> str:
        return f"{self.creature}: {self.mode} {self.trait}"


class GameGroupCreatureVampirePower(models.Model):
    creature = models.ForeignKey(
        "charsheet.GameGroupCreature",
        on_delete=models.CASCADE,
        related_name="vampire_power_overrides",
    )
    power = models.ForeignKey(
        VampirePower,
        on_delete=models.PROTECT,
        related_name="game_group_creature_overrides",
    )
    mode = models.CharField(max_length=12, choices=VampireTraitOverrideMode.choices, default=VampireTraitOverrideMode.ADD)
    purchased_without_weakness = models.BooleanField(blank=True, null=True)
    weakness_bought_off = models.BooleanField(blank=True, null=True)

    class Meta:
        ordering = ["creature", "power__sort_order", "power__name", "id"]
        verbose_name = "Game group creature vampire power"
        verbose_name_plural = "Game group creature vampire powers"
        constraints = [
            models.UniqueConstraint(fields=["creature", "power"], name="uniq_group_creature_vampire_power")
        ]

    def validation_warnings(self) -> list[str]:
        if self.mode == VampireTraitOverrideMode.REMOVE and (
            self.purchased_without_weakness is not None or self.weakness_bought_off is not None
        ):
            return ["A remove override ignores weakness values."]
        return []

    def __str__(self) -> str:
        return f"{self.creature}: {self.mode} {self.power}"
