"""Independent, character-owned KP stores granted by semantic effects."""

from charsheet.constants import ADDITIONAL_ARCANE_POWER


def arcane_pools(character):
    """Keep each concrete source separate, including identical owned items."""
    result = []
    current_values = character.additional_arcane_power_current or {}
    for modifier, capacity in (
        character.engine.modifier_engine.resolve_separate_stores(
            "derived_stat", ADDITIONAL_ARCANE_POWER,
        )
    ):
        metadata = modifier.metadata or {}
        effect_key = metadata.get("semantic_effect_key", "")
        owned_id = metadata.get("character_item_id")
        if modifier.source_type == "characteritem":
            owned_id = modifier.source_id
            effect_key = f"characteritem:{effect_key}"
        if owned_id:
            base_id = metadata.get("base_item_effect_id")
            if base_id:
                effect_key = f"item_effect:{base_id}"
            key = f"owned:{owned_id}:{effect_key}"
        else:
            key = (
                f"{modifier.source_type}:{modifier.source_id}:{effect_key}"
            )
        current = max(0, min(capacity, int(current_values.get(key, 0))))
        result.append({
            "key": key,
            "label": metadata.get("semantic_effect_label") or "KP-Vorrat",
            "current": current,
            "capacity": capacity,
            "percent": f"{current / capacity * 100:.2f}",
        })
    return result
