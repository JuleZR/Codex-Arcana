"""Shared vampire traits, semantic effects, and domain-specific ownership."""

from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from ..constants import (
    MODIFIER_OPERATOR_CHOICES,
    MODIFIER_VISIBILITY_CHOICES,
    STACK_BEHAVIOR_CHOICES,
)
from .creatures import CREATURE_TARGET_DOMAIN_CHOICES


VAMPIRE_TRAIT_TARGET_DOMAIN_CHOICES = CREATURE_TARGET_DOMAIN_CHOICES


class VampireTrait(models.Model):
    """One reusable rulebook entry shared by vampires in every actor domain."""

    class TraitType(models.TextChoices):
        POWER = "power", "Power"
        WEAKNESS = "weakness", "Weakness"

    class Handler(models.TextChoices):
        NONE = "", "No automated workflow"
        MANUAL_ACTIVATION = "manual_activation", "Activation and blood cost"
        BLOOD_THEFT = "blood_theft", "Blood theft"
        BLOOD_SACRAMENT = "blood_sacrament", "Blood sacrament"
        ATTRIBUTE_BOOST = "attribute_boost", "Blood-fuelled attribute boost"
        REGENERATION = "regeneration", "Regeneration"

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=150, unique=True)
    trait_type = models.CharField(max_length=20, choices=TraitType.choices)
    description = models.TextField(blank=True, default="")
    rules_text = models.TextField(blank=True, default="")
    point_value = models.PositiveSmallIntegerField(default=0)
    blood_cost = models.PositiveSmallIntegerField(blank=True, null=True)
    rankable = models.BooleanField(default=False)
    max_rank = models.PositiveSmallIntegerField(blank=True, null=True)
    handler = models.CharField(max_length=40, choices=Handler.choices, blank=True, default="")
    associated_weakness = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="associated_powers",
        blank=True,
        null=True,
        limit_choices_to={"trait_type": TraitType.WEAKNESS},
    )
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name", "id"]
        verbose_name = "Vampire trait"
        verbose_name_plural = "Vampire traits"

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        errors: dict[str, str] = {}
        if self.trait_type != self.TraitType.POWER:
            if self.blood_cost is not None:
                errors["blood_cost"] = "Only powers may have activation costs."
            if self.handler:
                errors["handler"] = "Only powers may have an activation handler."
            if self.associated_weakness_id:
                errors["associated_weakness"] = "Only powers may have an associated weakness."
            if self.rankable:
                errors["rankable"] = "Only powers may be rankable."
        if self.associated_weakness_id:
            weakness_type = getattr(self.associated_weakness, "trait_type", None)
            if weakness_type != self.TraitType.WEAKNESS:
                errors["associated_weakness"] = "The associated trait must be a vampire weakness."
        if not self.rankable and self.max_rank is not None:
            errors["max_rank"] = "A maximum rank is only valid for rankable traits."
        if self.rankable and self.max_rank is not None and self.max_rank < 1:
            errors["max_rank"] = "The maximum rank must be at least one."
        if errors:
            raise ValidationError(errors)

    def cost_for_rank(self, rank: int = 1) -> int:
        return int(self.point_value or 0) * max(1, int(rank or 1))


class VampireTraitSemanticEffect(models.Model):
    """Passive semantic effect contributed by one vampire trait."""

    class ApplicationScope(models.TextChoices):
        CHARACTER = "character", "Character"
        CREATURE = "creature", "Creature"
        BOTH = "both", "Character and creature"

    trait = models.ForeignKey(
        VampireTrait,
        on_delete=models.CASCADE,
        related_name="semantic_effects",
    )
    application_scope = models.CharField(
        max_length=20,
        choices=ApplicationScope.choices,
        default=ApplicationScope.BOTH,
    )
    sort_order = models.PositiveIntegerField(default=0)
    target_skills = models.ManyToManyField(
        "charsheet.Skill",
        blank=True,
        related_name="vampire_trait_semantic_effects",
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
        return f"{self.trait.name}: {self.target_domain}/{self.target_key} ({self.operator})"

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
        }
        metadata = {
            **dict(self.metadata or {}),
            "vampire_trait_slug": self.trait.slug,
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
            source_type="vampire_trait",
            source_id=str(self.trait_id),
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


def _validate_rank_and_buyoff(ownership, *, strict: bool) -> list[str]:
    """Return warnings, raising for strict character ownership."""
    warnings: list[str] = []
    trait = getattr(ownership, "trait", None)
    if trait is None:
        return warnings
    rank = int(getattr(ownership, "rank", None) or 1)
    if rank != 1 and not trait.rankable:
        warnings.append(f"{trait.name} is not rankable according to its definition.")
    if trait.max_rank is not None and rank > int(trait.max_rank):
        warnings.append(f"{trait.name} may not exceed rank {trait.max_rank}.")
    bought_off = getattr(ownership, "associated_weakness_bought_off", None)
    if bought_off and (trait.trait_type != VampireTrait.TraitType.POWER or not trait.associated_weakness_id):
        warnings.append("A weakness buyoff is only valid for a power with an associated weakness.")
    if strict and warnings:
        raise ValidationError({"trait": " ".join(warnings)})
    return warnings


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
        limit_choices_to={"trait_type__in": [VampireTrait.TraitType.POWER, VampireTrait.TraitType.WEAKNESS]},
    )
    rank = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    associated_weakness_bought_off = models.BooleanField(default=False)

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
        _validate_rank_and_buyoff(self, strict=True)

    def __str__(self) -> str:
        return f"{self.character}: {self.trait} ({self.rank})"


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
    rank = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    associated_weakness_bought_off = models.BooleanField(default=False)

    class Meta:
        ordering = ["creature", "trait__sort_order", "trait__name", "id"]
        verbose_name = "Creature vampire trait"
        verbose_name_plural = "Creature vampire traits"
        constraints = [
            models.UniqueConstraint(fields=["creature", "trait"], name="uniq_creature_vampire_trait")
        ]

    def validation_warnings(self) -> list[str]:
        return _validate_rank_and_buyoff(self, strict=False)

    def __str__(self) -> str:
        return f"{self.creature}: {self.trait} ({self.rank})"


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
    rank = models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1)])
    associated_weakness_bought_off = models.BooleanField(blank=True, null=True)

    class Meta:
        ordering = ["creature", "trait__sort_order", "trait__name", "id"]
        verbose_name = "Character creature vampire trait"
        verbose_name_plural = "Character creature vampire traits"
        constraints = [
            models.UniqueConstraint(fields=["creature", "trait"], name="uniq_character_creature_vampire_trait")
        ]

    def validation_warnings(self) -> list[str]:
        warnings = _validate_rank_and_buyoff(self, strict=False)
        if self.mode == VampireTraitOverrideMode.REMOVE and (
            self.rank is not None or self.associated_weakness_bought_off is not None
        ):
            warnings.append("A remove override ignores rank and weakness buyoff values.")
        return warnings

    def __str__(self) -> str:
        return f"{self.creature}: {self.mode} {self.trait}"


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
    rank = models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1)])
    associated_weakness_bought_off = models.BooleanField(blank=True, null=True)

    class Meta:
        ordering = ["creature", "trait__sort_order", "trait__name", "id"]
        verbose_name = "Game group creature vampire trait"
        verbose_name_plural = "Game group creature vampire traits"
        constraints = [
            models.UniqueConstraint(fields=["creature", "trait"], name="uniq_group_creature_vampire_trait")
        ]

    def validation_warnings(self) -> list[str]:
        warnings = _validate_rank_and_buyoff(self, strict=False)
        if self.mode == VampireTraitOverrideMode.REMOVE and (
            self.rank is not None or self.associated_weakness_bought_off is not None
        ):
            warnings.append("A remove override ignores rank and weakness buyoff values.")
        return warnings

    def __str__(self) -> str:
        return f"{self.creature}: {self.mode} {self.trait}"
