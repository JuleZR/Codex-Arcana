"""Compatibility adapters for the legacy Django Modifier model."""

from __future__ import annotations

from charsheet.modifiers.definitions import BaseModifier
from charsheet.modifiers.migration import LegacyModifierMigrationService
from charsheet.models import Modifier


class LegacyModifierAdapter:
    """Translate persisted legacy modifier rows into typed domain modifiers."""

    @staticmethod
    def adapt(legacy_modifier: Modifier) -> BaseModifier:
        """Return the closest new modifier specialization for one legacy row."""
        record = LegacyModifierMigrationService([legacy_modifier]).migrate_modifier(legacy_modifier)
        migrated = record.primary_modifier()
        if migrated is not None:
            return migrated

        return BaseModifier(
            source_type=legacy_modifier.source_content_type.model,
            source_id=str(legacy_modifier.source_object_id),
            target_domain="metadata",
            target_key=str(legacy_modifier.target_identifier()),
            mode=legacy_modifier.mode,
            value=legacy_modifier.value,
            notes=record.migration_note,
            metadata={
                "legacy_modifier": legacy_modifier,
                "legacy_modifier_id": legacy_modifier.id,
                "requires_manual_review": True,
                "migration_strategy": record.migration_strategy,
            },
        )
