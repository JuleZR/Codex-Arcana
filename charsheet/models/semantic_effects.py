"""Helpers for persisted SemanticEffect models."""

from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.db import models

from ..constants import (
    MODIFIER_OPERATOR_CHOICES,
    MODIFIER_VISIBILITY_CHOICES,
    STACK_BEHAVIOR_CHOICES,
    TARGET_DOMAIN_CHOICES,
)


def coerce_semantic_scalar(raw_value):
    """Coerce admin-entered text into bool, int, float, JSON, or plain text."""
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


class SemanticEffectFields(models.Model):
    """Shared fields for new persisted semantic-effect source tables."""

    sort_order = models.PositiveIntegerField(default=0)
    target_domain = models.CharField(max_length=40, choices=TARGET_DOMAIN_CHOICES, default="rule_flag")
    target_key = models.CharField(max_length=120, blank=True, default="")
    operator = models.CharField(max_length=40, choices=MODIFIER_OPERATOR_CHOICES, default="flat_add")
    mode = models.CharField(max_length=20, default="flat")
    value = models.CharField(max_length=200, blank=True, default="")
    value_min = models.IntegerField(null=True, blank=True)
    value_max = models.IntegerField(null=True, blank=True)
    formula = models.CharField(max_length=200, blank=True, default="")
    scaling = models.JSONField(default=dict, blank=True)
    stack_behavior = models.CharField(max_length=40, choices=STACK_BEHAVIOR_CHOICES, default="stack")
    condition_set = models.JSONField(default=dict, blank=True)
    condition_races = models.ManyToManyField(
        "charsheet.Race",
        blank=True,
        related_name="%(app_label)s_%(class)s_conditioned_effects",
        help_text="Optional race condition. Leave empty to apply to every race.",
    )
    condition_schools = models.ManyToManyField(
        "charsheet.School",
        blank=True,
        related_name="%(app_label)s_%(class)s_school_conditioned_effects",
        help_text="Optional school condition. Leave empty to apply to every school.",
    )
    active_flag = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)
    notes = models.TextField(blank=True, default="")
    rules_text = models.TextField(blank=True, default="")
    visibility = models.CharField(max_length=20, choices=MODIFIER_VISIBILITY_CHOICES, default="public")
    hidden = models.BooleanField(default=False)
    sheet_relevant = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        for field_name in ("scaling", "condition_set", "metadata"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, dict):
                raise ValidationError({field_name: "Value must be a JSON object."})

    def semantic_source_type(self) -> str:
        raise NotImplementedError

    def semantic_source_id(self) -> str:
        raise NotImplementedError

    def semantic_source_label(self) -> str:
        raise NotImplementedError

    def semantic_effect_key_prefix(self) -> str:
        raise NotImplementedError

    def to_modifier(self):
        """Materialize this persisted row as a typed modifier."""
        from ..modifiers.definitions import ConditionSet
        from ..modifiers.targets import TargetResolver

        metadata = dict(self.metadata or {})
        if self.pk:
            metadata["semantic_effect_key"] = f"{self.semantic_effect_key_prefix()}:{self.pk}"
            metadata["semantic_effect_label"] = self.semantic_source_label()
            condition_race_ids = list(self.condition_races.order_by("id").values_list("id", flat=True))
            if condition_race_ids:
                metadata["condition_race_ids"] = condition_race_ids
            condition_school_ids = list(
                self.condition_schools.order_by("id").values_list("id", flat=True)
            )
            if condition_school_ids:
                metadata["condition_school_ids"] = condition_school_ids
        resolved_target = TargetResolver.resolve(self.target_domain, self.target_key, metadata)
        for key, values in resolved_target.context_requirements.items():
            if key == "weapon_types":
                metadata.setdefault("target_weapon_type", list(values))
            elif key == "weapon_skill_slugs":
                metadata.setdefault("target_weapon_skill", list(values))
            elif key == "weapon_categories":
                metadata.setdefault("target_weapon_category", list(values))
            elif key == "weapon_ids":
                metadata.setdefault("target_weapon_id", list(values))
        modifier_cls = semantic_modifier_class(resolved_target.domain)
        return modifier_cls(
            source_type=self.semantic_source_type(),
            source_id=self.semantic_source_id(),
            target_domain=resolved_target.domain,
            target_key=resolved_target.key,
            mode=self.mode,
            value=coerce_semantic_scalar(self.value),
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


def semantic_modifier_class(target_domain):
    """Return the typed modifier class for one target domain."""
    from ..modifiers.definitions import (
        AttributeCapModifier,
        AttributeModifier,
        BaseModifier,
        CombatModifier,
        CreatureMovementModifier,
        DerivedStatModifier,
        EconomyModifier,
        EntityModifier,
        ItemModifier,
        LanguageModifier,
        MovementModifier,
        PerceptionModifier,
        ProficiencyGroupModifier,
        ResourceModifier,
        ResistanceModifier,
        RuleFlagModifier,
        SkillModifier,
        SocialModifier,
        SpecializationModifier,
        TraitModifier,
        WeaponRangeModifier,
    )

    return {
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
        "creature_movement": CreatureMovementModifier,
        "combat": CombatModifier,
        "damage": CombatModifier,
        "weapon_range": WeaponRangeModifier,
        "perception": PerceptionModifier,
        "economy": EconomyModifier,
        "social": SocialModifier,
        "rule_flag": RuleFlagModifier,
        "item": ItemModifier,
        "item_category": ItemModifier,
        "specialization": SpecializationModifier,
        "entity": EntityModifier,
    }.get(str(target_domain or ""), BaseModifier)
