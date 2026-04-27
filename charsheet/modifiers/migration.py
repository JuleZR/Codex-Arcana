"""Inventory, mapping, and compatibility services for legacy modifiers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from typing import Any, Iterable

from django.apps import apps

from charsheet.modifiers.definitions import (
    AttributeModifier,
    BaseModifier,
    CombatModifier,
    DerivedStatModifier,
    EntityModifier,
    ItemModifier,
    ModifierOperator,
    RuleFlagModifier,
    SkillModifier,
    SpecializationModifier,
    TargetDomain,
)
from charsheet.constants import ATTRIBUTE_CODE_CHOICES
from charsheet.models import Modifier, Skill


class ModifierResolutionMode(str, Enum):
    """Internal debug switch for the central modifier engine."""

    NEW_ONLY = "new_only"
    COMPARE = "compare"

    @classmethod
    def normalize(cls, value: str | None):
        """Return a valid mode string with new-only as safe default."""
        if isinstance(value, cls):
            return value
        raw_value = getattr(value, "value", value)
        normalized = str(raw_value or cls.NEW_ONLY.value).strip().lower()
        for member in cls:
            if normalized == str(member.value):
                return member
        return cls.NEW_ONLY


class MigrationConfidence(str, Enum):
    """Confidence level for an automatic legacy-to-new mapping."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MigrationStrategy(str, Enum):
    """How one legacy modifier enters the new system."""

    AUTO_TYPED = "auto_typed"
    ADAPTER_ONLY = "adapter_only"
    REVIEW_REQUIRED = "review_required"


LEGACY_CODE_READERS = (
    ("charsheet/engine/character_engine.py", "Loads persisted legacy rows as source data and routes productive resolution through ModifierEngine."),
    ("charsheet/engine/character_combat.py", "Consumes CharacterEngine outputs whose modifier portions now come from ModifierEngine."),
    ("charsheet/engine/character_equipment.py", "Consumes CharacterEngine outputs whose modifier portions now come from ModifierEngine."),
    ("charsheet/sheet_context.py", "Displays values resolved by CharacterEngine; no direct modifier math."),
    ("charsheet/admin.py", "Maintains legacy modifier rows and choice-definition targeting."),
)


@dataclass(slots=True)
class LegacyModifierRelation:
    """One model-field relation touching the legacy modifier model."""

    direction: str
    model_name: str
    field_name: str
    relation_kind: str
    related_model_name: str


@dataclass(slots=True)
class LegacyModifierInventoryRow:
    """Flattened inventory row for one persisted legacy modifier."""

    legacy_modifier_id: int
    source_model: str
    source_object_id: int
    target_kind: str
    target_slug: str
    target_identifier: str
    mode: str
    value: int
    scale_source: str | None
    cap_mode: str
    usage_signature: str
    notes: tuple[str, ...] = ()


@dataclass(slots=True)
class LegacyModifierMigrationRecord:
    """Migration mapping for one legacy modifier row."""

    legacy_modifier_id: int
    legacy_model_name: str
    previous_meaning: str
    new_modifier_type: str
    new_target_domain: str
    migration_strategy: str
    migration_confidence: str
    requires_manual_review: bool
    migration_note: str
    risk: str
    migrated_from_legacy: bool = True
    migrated_modifiers: tuple[BaseModifier, ...] = ()

    def primary_modifier(self) -> BaseModifier | None:
        """Return the primary migrated modifier if one exists."""
        if not self.migrated_modifiers:
            return None
        return self.migrated_modifiers[0]


@dataclass(slots=True)
class NumericResolutionComparison:
    """Comparison row between legacy and migrated numeric resolution."""

    target_domain: str
    target_key: str
    legacy_value: int
    new_value: int
    matches: bool
    classification: str
    notes: tuple[str, ...] = ()


class LegacyModifierMigrationService:
    """Inventory and map persisted legacy modifier rows into new typed modifiers."""

    KNOWN_DERIVED_STATS = {"initiative", "arcane_power", "potential", "wound_stage", "wound_penalty_mod", "vw", "gw", "sr", "rs"}
    KNOWN_RULE_FLAGS = {"wound_penalty_ignore", "armor_penalty_ignore", "shield_penalty_ignore"}
    DAMAGE_SLUG_PREFIX = "dmg_"
    KNOWN_ATTRIBUTES = {value for value, _label in ATTRIBUTE_CODE_CHOICES}

    def __init__(self, legacy_modifiers: Iterable[Modifier] | None = None):
        self._legacy_modifiers = list(legacy_modifiers) if legacy_modifiers is not None else None

    @cached_property
    def legacy_modifiers(self) -> list[Modifier]:
        """Return the legacy modifier rows this service inventories."""
        if self._legacy_modifiers is not None:
            return list(self._legacy_modifiers)
        return list(
            Modifier.objects.select_related(
                "source_content_type",
                "target_skill",
                "target_skill_category",
                "target_item",
                "target_specialization",
                "target_choice_definition",
                "target_race_choice_definition",
                "target_content_type",
                "scale_school",
                "scale_skill",
            ).order_by("id")
        )

    def inventory_rows(self) -> list[LegacyModifierInventoryRow]:
        """Return a flattened inventory of all persisted legacy modifiers."""
        rows: list[LegacyModifierInventoryRow] = []
        for modifier in self.legacy_modifiers:
            notes: list[str] = []
            if modifier.target_choice_definition_id:
                notes.append("targets technique choice definition")
            if modifier.target_race_choice_definition_id:
                notes.append("targets race choice definition")
            if self._is_damage_slug(modifier.target_slug or modifier.target_identifier()):
                notes.append("damage-style slug")
            if modifier.target_kind == Modifier.TargetKind.SKILL and not self._skill_selector_resolves(modifier):
                notes.append("skill target does not resolve to a persisted skill")
            rows.append(
                LegacyModifierInventoryRow(
                    legacy_modifier_id=int(modifier.id),
                    source_model=str(modifier.source_content_type.model),
                    source_object_id=int(modifier.source_object_id),
                    target_kind=str(modifier.target_kind),
                    target_slug=str(modifier.target_slug or ""),
                    target_identifier=str(self._legacy_target_identifier(modifier)),
                    mode=str(modifier.mode),
                    value=int(modifier.value),
                    scale_source=modifier.scale_source or None,
                    cap_mode=str(modifier.cap_mode),
                    usage_signature=(
                        f"{modifier.target_kind}:{self._legacy_target_identifier(modifier)}"
                        f"|{modifier.mode}|{modifier.scale_source or '-'}|{modifier.cap_mode}"
                    ),
                    notes=tuple(notes),
                )
            )
        return rows

    def relationship_inventory(self) -> list[LegacyModifierRelation]:
        """Return model-field relationships touching the legacy modifier model."""
        relations: list[LegacyModifierRelation] = []
        for field in Modifier._meta.get_fields():
            if not getattr(field, "is_relation", False):
                continue
            if field.auto_created:
                continue
            related_model = getattr(field, "related_model", None)
            relations.append(
                LegacyModifierRelation(
                    direction="outgoing",
                    model_name="charsheet.Modifier",
                    field_name=field.name,
                    relation_kind=field.__class__.__name__,
                    related_model_name=self._model_label(related_model),
                )
            )

        for model in apps.get_models():
            for field in model._meta.get_fields():
                if not getattr(field, "is_relation", False):
                    continue
                related_model = getattr(field, "related_model", None)
                if related_model is not Modifier:
                    continue
                relations.append(
                    LegacyModifierRelation(
                        direction="incoming",
                        model_name=self._model_label(model),
                        field_name=field.name,
                        relation_kind=field.__class__.__name__,
                        related_model_name="charsheet.Modifier",
                    )
                )
        return relations

    def code_reader_inventory(self) -> tuple[tuple[str, str], ...]:
        """Return known code paths that still read or present legacy modifiers."""
        return LEGACY_CODE_READERS

    def migration_records(self) -> list[LegacyModifierMigrationRecord]:
        """Return migration mappings for all legacy modifiers."""
        return list(self._migration_records)

    @cached_property
    def _migration_records(self) -> tuple[LegacyModifierMigrationRecord, ...]:
        """Cache migration mappings for all legacy modifiers."""
        return tuple(self.migrate_modifier(modifier) for modifier in self.legacy_modifiers)

    def migrate_modifier(self, legacy_modifier: Modifier) -> LegacyModifierMigrationRecord:
        """Map one legacy modifier row to the best new typed modifier."""
        previous_meaning = self._describe_legacy_meaning(legacy_modifier)
        classification = self._classify(legacy_modifier)

        migrated_modifier: BaseModifier | None = None
        if classification["modifier_cls"] is not None:
            migrated_modifier = self._build_migrated_modifier(legacy_modifier, classification)

        return LegacyModifierMigrationRecord(
            legacy_modifier_id=int(legacy_modifier.id),
            legacy_model_name="charsheet.Modifier",
            previous_meaning=previous_meaning,
            new_modifier_type=classification["modifier_type"],
            new_target_domain=classification["target_domain"],
            migration_strategy=classification["migration_strategy"],
            migration_confidence=classification["migration_confidence"],
            requires_manual_review=classification["requires_manual_review"],
            migration_note=classification["migration_note"],
            risk=classification["risk"],
            migrated_modifiers=((migrated_modifier,) if migrated_modifier is not None else ()),
        )

    def summarize_combinations(self) -> list[dict[str, Any]]:
        """Return grouped inventory by real target/mode combinations."""
        grouped: dict[tuple[str, str, str, str], int] = {}
        for row in self.inventory_rows():
            key = (row.target_kind, row.target_identifier, row.mode, row.scale_source or "-")
            grouped[key] = grouped.get(key, 0) + 1
        return [
            {
                "target_kind": target_kind,
                "target_identifier": target_identifier,
                "mode": mode,
                "scale_source": scale_source,
                "count": count,
            }
            for (target_kind, target_identifier, mode, scale_source), count in sorted(grouped.items())
        ]

    def _build_migrated_modifier(self, legacy_modifier: Modifier, classification: dict[str, Any]) -> BaseModifier:
        """Create the new typed modifier object with provenance metadata."""
        magnitude = abs(int(legacy_modifier.value))
        operator = ModifierOperator.FLAT_SUB if int(legacy_modifier.value) < 0 else ModifierOperator.FLAT_ADD
        if classification["target_domain"] == TargetDomain.RULE_FLAG:
            operator = ModifierOperator.SET_FLAG if int(legacy_modifier.value) else ModifierOperator.UNSET_FLAG
            magnitude = bool(int(legacy_modifier.value))

        metadata = {
            "legacy_modifier": legacy_modifier,
            "legacy_modifier_id": int(legacy_modifier.id),
            "legacy_model_name": "charsheet.Modifier",
            "migrated_from_legacy": True,
            "migration_note": classification["migration_note"],
            "migration_confidence": classification["migration_confidence"],
            "requires_manual_review": classification["requires_manual_review"],
            "migration_strategy": classification["migration_strategy"],
            "legacy_target_kind": legacy_modifier.target_kind,
            "legacy_target_slug": legacy_modifier.target_slug,
            "legacy_target_identifier": self._legacy_target_identifier(legacy_modifier),
            "legacy_source_model": legacy_modifier.source_content_type.model,
            "legacy_source_object_id": legacy_modifier.source_object_id,
            "choice_binding": self._choice_binding_payload(legacy_modifier),
        }

        modifier_cls = classification["modifier_cls"]
        effect_note = (legacy_modifier.effect_description or "").strip()
        note_text = effect_note or classification["migration_note"]
        return modifier_cls(
            source_type=str(legacy_modifier.source_content_type.model),
            source_id=str(legacy_modifier.source_object_id),
            target_domain=classification["target_domain"],
            target_key=self._migrated_target_key(legacy_modifier),
            mode=str(legacy_modifier.mode),
            value=magnitude,
            scaling={
                "scale_source": legacy_modifier.scale_source,
                "scale_school_id": legacy_modifier.scale_school_id,
                "scale_skill_id": legacy_modifier.scale_skill_id,
                "mul": legacy_modifier.mul,
                "div": legacy_modifier.div,
                "round_mode": legacy_modifier.round_mode,
                "cap_mode": legacy_modifier.cap_mode,
                "cap_source": legacy_modifier.cap_source,
                "min_school_level": legacy_modifier.min_school_level,
            },
            operator=operator,
            notes=note_text,
            metadata=metadata,
        )

    def _classify(self, legacy_modifier: Modifier) -> dict[str, Any]:
        """Return semantic mapping metadata for one legacy row."""
        requires_manual_review = False
        migration_note = "Mapped automatically from legacy modifier semantics."
        risk = "low"
        confidence = MigrationConfidence.HIGH
        strategy = MigrationStrategy.AUTO_TYPED
        modifier_cls = BaseModifier
        target_domain = TargetDomain.METADATA
        modifier_type = "BaseModifier"

        legacy_slug = str(self._legacy_target_identifier(legacy_modifier))

        if legacy_modifier.target_kind == Modifier.TargetKind.SKILL:
            if legacy_modifier.target_choice_definition_id or legacy_modifier.target_race_choice_definition_id:
                target_domain = TargetDomain.SKILL
                modifier_cls = SkillModifier
                modifier_type = "SkillModifier"
                migration_note = "Choice-bound skill modifier; migrated with dynamic selection binding metadata."
                confidence = MigrationConfidence.MEDIUM
                risk = "medium"
            elif self._is_damage_slug(legacy_slug):
                target_domain = TargetDomain.COMBAT
                modifier_cls = CombatModifier
                modifier_type = "CombatModifier"
                migration_note = (
                    "Legacy target_kind=skill uses a damage slug. Migrated as combat modifier for backward-compatible combat resolution."
                )
                confidence = MigrationConfidence.MEDIUM
                risk = "medium"
            elif self._skill_selector_resolves(legacy_modifier):
                target_domain = TargetDomain.SKILL
                modifier_cls = SkillModifier
                modifier_type = "SkillModifier"
            else:
                target_domain = TargetDomain.SKILL
                modifier_cls = SkillModifier
                modifier_type = "SkillModifier"
                migration_note = "Skill target could not be matched to a persisted skill; review required."
                confidence = MigrationConfidence.LOW
                requires_manual_review = True
                strategy = MigrationStrategy.REVIEW_REQUIRED
                risk = "high"

        elif legacy_modifier.target_kind == Modifier.TargetKind.CATEGORY:
            target_domain = TargetDomain.SKILL_CATEGORY
            modifier_cls = SkillModifier
            modifier_type = "SkillModifier"

        elif legacy_modifier.target_kind == Modifier.TargetKind.ATTRIBUTE:
            target_domain = TargetDomain.ATTRIBUTE
            modifier_cls = AttributeModifier
            modifier_type = "AttributeModifier"

        elif legacy_modifier.target_kind == Modifier.TargetKind.STAT:
            if legacy_slug in self.KNOWN_ATTRIBUTES:
                target_domain = TargetDomain.ATTRIBUTE
                modifier_cls = AttributeModifier
                modifier_type = "AttributeModifier"
            elif legacy_slug in self.KNOWN_DERIVED_STATS:
                target_domain = TargetDomain.DERIVED_STAT
                modifier_cls = DerivedStatModifier
                modifier_type = "DerivedStatModifier"
            elif legacy_slug in self.KNOWN_RULE_FLAGS:
                target_domain = TargetDomain.RULE_FLAG
                modifier_cls = RuleFlagModifier
                modifier_type = "RuleFlagModifier"
                if legacy_slug == "shield_penalty_ignore":
                    migration_note = "Flag migrated automatically into the central rule-flag resolution."
            elif self._is_damage_slug(legacy_slug):
                target_domain = TargetDomain.COMBAT
                modifier_cls = CombatModifier
                modifier_type = "CombatModifier"
                migration_note = "Damage-style stat slug migrated as combat modifier."
                confidence = MigrationConfidence.MEDIUM
                risk = "medium"
            else:
                target_domain = TargetDomain.METADATA
                modifier_cls = BaseModifier
                modifier_type = "BaseModifier"
                migration_note = "Unknown stat-like target slug; manual classification required."
                confidence = MigrationConfidence.LOW
                requires_manual_review = True
                strategy = MigrationStrategy.REVIEW_REQUIRED
                risk = "high"

        elif legacy_modifier.target_kind == Modifier.TargetKind.ITEM:
            target_domain = TargetDomain.ITEM
            modifier_cls = ItemModifier
            modifier_type = "ItemModifier"

        elif legacy_modifier.target_kind == Modifier.TargetKind.ITEM_CATEGORY:
            target_domain = TargetDomain.ITEM_CATEGORY
            modifier_cls = ItemModifier
            modifier_type = "ItemModifier"
            confidence = MigrationConfidence.MEDIUM
            risk = "medium"

        elif legacy_modifier.target_kind == Modifier.TargetKind.SPECIALIZATION:
            target_domain = TargetDomain.SPECIALIZATION
            modifier_cls = SpecializationModifier
            modifier_type = "SpecializationModifier"

        elif legacy_modifier.target_kind == Modifier.TargetKind.ENTITY:
            target_domain = TargetDomain.ENTITY
            modifier_cls = EntityModifier
            modifier_type = "EntityModifier"

        return {
            "target_domain": target_domain,
            "modifier_cls": modifier_cls,
            "modifier_type": modifier_type,
            "migration_strategy": strategy,
            "migration_confidence": confidence,
            "requires_manual_review": requires_manual_review,
            "migration_note": migration_note,
            "risk": risk,
        }

    def _legacy_target_identifier(self, legacy_modifier: Modifier) -> str:
        """Return a stable identifier for reporting legacy targets."""
        if legacy_modifier.target_choice_definition_id:
            return f"technique_choice_definition:{legacy_modifier.target_choice_definition_id}"
        if legacy_modifier.target_race_choice_definition_id:
            return f"race_choice_definition:{legacy_modifier.target_race_choice_definition_id}"
        return legacy_modifier.target_identifier()

    def _migrated_target_key(self, legacy_modifier: Modifier) -> str:
        """Return the new-system target key for one legacy row."""
        legacy_slug = str(self._legacy_target_identifier(legacy_modifier))
        if legacy_modifier.target_choice_definition_id:
            return f"selected_skill:technique_choice_definition:{legacy_modifier.target_choice_definition_id}"
        if legacy_modifier.target_race_choice_definition_id:
            return f"selected_skill:race_choice_definition:{legacy_modifier.target_race_choice_definition_id}"
        return legacy_slug

    def _choice_binding_payload(self, legacy_modifier: Modifier) -> dict[str, Any] | None:
        """Return dynamic choice-binding metadata when present."""
        if legacy_modifier.target_choice_definition_id:
            return {"kind": "technique_choice_definition", "id": int(legacy_modifier.target_choice_definition_id)}
        if legacy_modifier.target_race_choice_definition_id:
            return {"kind": "race_choice_definition", "id": int(legacy_modifier.target_race_choice_definition_id)}
        return None

    def _describe_legacy_meaning(self, legacy_modifier: Modifier) -> str:
        """Return a concise human-readable description of the legacy row."""
        target_identifier = self._legacy_target_identifier(legacy_modifier)
        source_label = f"{legacy_modifier.source_content_type.model}#{legacy_modifier.source_object_id}"
        scale_suffix = f", scale={legacy_modifier.scale_source}" if legacy_modifier.scale_source else ""
        return (
            f"{source_label} applies {legacy_modifier.mode} value {legacy_modifier.value} "
            f"to {legacy_modifier.target_kind}:{target_identifier}{scale_suffix}"
        )

    def _skill_selector_resolves(self, legacy_modifier: Modifier) -> bool:
        """Return whether a legacy skill target resolves to a persisted skill."""
        if legacy_modifier.target_skill_id:
            return True
        slug = legacy_modifier.target_slug or ""
        if not slug:
            return False
        return Skill.objects.filter(slug=slug).exists()

    def _is_damage_slug(self, slug: str) -> bool:
        """Return whether a slug looks like a combat damage modifier key."""
        return str(slug or "").startswith(self.DAMAGE_SLUG_PREFIX)

    def _model_label(self, model) -> str:
        """Return app_label.ModelName style labels for report output."""
        if model is None:
            return "-"
        return f"{model._meta.app_label}.{model.__name__}"
