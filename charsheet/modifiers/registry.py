"""Trait-centered semantic modifier registry."""

from __future__ import annotations

from collections.abc import Callable

from charsheet.models import Trait
from charsheet.modifiers.definitions import (
    ConditionSet,
    DerivedStatModifier,
    EconomyModifier,
    ModifierOperator,
    ResourceModifier,
    ResistanceModifier,
    RuleFlagModifier,
    SocialModifier,
    TargetDomain,
)


def normalize_rule_slug(value: str) -> str:
    """Normalize German-ish slugs to a stable lookup form."""
    return (
        str(value or "")
        .lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
        .replace(" ", "_")
        .replace("-", "_")
    )


def _blind(level: int):
    return [
        RuleFlagModifier(
            source_type="trait",
            source_id="blind",
            target_key="blind",
            operator=ModifierOperator.SET_FLAG,
            value=True,
            notes="Complete loss of sight",
        ),
        RuleFlagModifier(
            source_type="trait",
            source_id="blind",
            target_domain=TargetDomain.CAPABILITY,
            target_key="can_see",
            operator=ModifierOperator.REMOVE_CAPABILITY,
            value=False,
            notes="Complete loss of sight",
        ),
    ]


def _deaf(level: int):
    return [
        RuleFlagModifier(
            source_type="trait",
            source_id="taub",
            target_key="deaf",
            operator=ModifierOperator.SET_FLAG,
            value=True,
        ),
        RuleFlagModifier(
            source_type="trait",
            source_id="taub",
            target_domain=TargetDomain.CAPABILITY,
            target_key="can_hear",
            operator=ModifierOperator.REMOVE_CAPABILITY,
            value=False,
        ),
    ]


def _mute(level: int):
    return [
        RuleFlagModifier(
            source_type="trait",
            source_id="stumm",
            target_key="mute",
            operator=ModifierOperator.SET_FLAG,
            value=True,
        ),
        RuleFlagModifier(
            source_type="trait",
            source_id="stumm",
            target_domain=TargetDomain.CAPABILITY,
            target_key="can_speak",
            operator=ModifierOperator.REMOVE_CAPABILITY,
            value=False,
        ),
    ]


def _slow(level: int):
    return [
        DerivedStatModifier(
            source_type="trait",
            source_id="langsam",
            target_key="initiative",
            operator=ModifierOperator.FLAT_SUB,
            value=max(1, level // 2),
            notes="Langsam lowers initiative by one per two points.",
        )
    ]


def _reduced_arcane_power(level: int):
    return [
        ResourceModifier(
            source_type="trait",
            source_id="verringerte_arkane_macht",
            target_key="arcane_power",
            operator=ModifierOperator.FLAT_SUB,
            value=level,
        )
    ]


def _heat_vulnerability(level: int):
    return [
        ResistanceModifier(
            source_type="trait",
            source_id="hitzeempfindlichkeit",
            target_key="natural_heat",
            operator=ModifierOperator.GRANT_VULNERABILITY,
            value=level * 2,
            notes="Natural heat vulnerability per GRW wording.",
        ),
        ResistanceModifier(
            source_type="trait",
            source_id="hitzeempfindlichkeit",
            target_key="magic_heat",
            operator=ModifierOperator.GRANT_VULNERABILITY,
            value=max(1, level // 2),
            notes="Reduced resistance against magical fire/heat.",
        ),
    ]


def _cold_vulnerability(level: int):
    return [
        ResistanceModifier(
            source_type="trait",
            source_id="kaelteempfindlichkeit",
            target_key="natural_cold",
            operator=ModifierOperator.GRANT_VULNERABILITY,
            value=level * 2,
        ),
        ResistanceModifier(
            source_type="trait",
            source_id="kaelteempfindlichkeit",
            target_key="magic_cold",
            operator=ModifierOperator.GRANT_VULNERABILITY,
            value=max(1, level // 2),
        ),
    ]


def _regular_income(level: int):
    return [
        EconomyModifier(
            source_type="trait",
            source_id="adv_regularincome",
            target_key="regular_income",
            operator=ModifierOperator.CHANGE_STARTING_FUNDS,
            value=level,
            notes="Represents recurring income rather than a flat skill/stat bonus.",
        )
    ]


_RICHES_GM_BY_LEVEL = {
    1: 50,
    2: 100,
    3: 250,
    4: 500,
    5: 1000,
    6: 2000,
    7: 4000,
    8: 8000,
}


def riches_gold_value(level: int) -> int:
    """Return the riches advantage payout in GM for one purchased level."""
    if level <= 0:
        return 0
    if level <= 8:
        return _RICHES_GM_BY_LEVEL[level]
    return _RICHES_GM_BY_LEVEL[8] + ((level - 8) * 4000)


def riches_internal_money_value(level: int) -> int:
    """Convert the GRW riches table from GM into the internal copper-like wallet unit."""
    return riches_gold_value(level) * 100


def _riches(level: int):
    gm_value = riches_gold_value(level)
    return [
        EconomyModifier(
            source_type="trait",
            source_id="adv_riches",
            target_key="starting_funds",
            operator=ModifierOperator.CHANGE_STARTING_FUNDS,
            value=riches_internal_money_value(level),
            condition_set=ConditionSet(applies_during_character_creation=True),
            notes="One-time starting wealth from Reichtuemer; cash or goods by player choice.",
            metadata={
                "currency": "GM",
                "display_value_gm": gm_value,
                "allocation_mode": "cash_or_goods",
            },
        )
    ]


def _noble(level: int):
    return [
        SocialModifier(
            source_type="trait",
            source_id="adel",
            target_key="status",
            operator=ModifierOperator.CHANGE_SOCIAL_STATUS,
            value=level,
            notes="Noble standing or heroic lineage.",
        )
    ]


def _wanted(level: int):
    return [
        SocialModifier(
            source_type="trait",
            source_id="gesuchter_verbrecher",
            target_key="legal_status",
            operator=ModifierOperator.ADD_TAG,
            value="wanted",
            notes="Character is a wanted criminal.",
        )
    ]


def _patron(level: int):
    return [
        SocialModifier(
            source_type="trait",
            source_id="patron",
            target_key="relationship",
            operator=ModifierOperator.ADD_TAG,
            value="patron",
        )
    ]


def _rival(level: int):
    return [
        SocialModifier(
            source_type="trait",
            source_id="rivale",
            target_key="relationship",
            operator=ModifierOperator.ADD_TAG,
            value="rival",
        )
    ]


def _behavioral(rule_key: str, label: str) -> Callable[[int], list]:
    def builder(level: int):
        return [
            RuleFlagModifier(
                source_type="trait",
                source_id=rule_key,
                target_domain=TargetDomain.BEHAVIOR,
                target_key=rule_key,
                operator=ModifierOperator.ADD_TAG,
                value=label,
                notes="Primarily roleplay / SL-facing constraint.",
                sheet_relevant=True,
                visibility="story",
            )
        ]

    return builder


def _persisted_trait_semantic_modifiers(*, trait=None, trait_slug: str = "") -> list:
    """Load persisted semantic effects for one trait from the admin-managed data model."""
    resolved_trait = trait
    if resolved_trait is None and trait_slug:
        resolved_trait = (
            Trait.objects.filter(slug=trait_slug)
            .prefetch_related("semantic_effects")
            .first()
        )
    if resolved_trait is None:
        return []
    if getattr(resolved_trait, "pk", None) is None:
        return []
    effect_rows = list(getattr(resolved_trait, "semantic_effects").all())
    return [effect.to_modifier() for effect in effect_rows if effect.active_flag]


TRAIT_SEMANTIC_BUILDERS: dict[str, Callable[[int], list]] = {
    "blind": _blind,
    "taub": _deaf,
    "stumm": _mute,
    "langsam": _slow,
    "verringerte_arkane_macht": _reduced_arcane_power,
    "hitzeempfindlichkeit": _heat_vulnerability,
    "kaelteempfindlichkeit": _cold_vulnerability,
    "adv_riches": _riches,
    "reichtuemer": _riches,
    "regelmaessiges_einkommen": _regular_income,
    "adv_regularincome": _regular_income,
    "adel": _noble,
    "heldensohn": _noble,
    "gesuchter_verbrecher": _wanted,
    "patron": _patron,
    "rivale": _rival,
    "macke": _behavioral("macke", "behavioral_constraint"),
    "phobie": _behavioral("phobie", "behavioral_constraint"),
    "geluebde": _behavioral("geluebde", "behavioral_constraint"),
    "fanatiker": _behavioral("fanatiker", "behavioral_constraint"),
}


def build_trait_semantic_modifiers(*, trait_slug: str, level: int, trait=None, allow_persisted_lookup: bool = True) -> list:
    """Return semantic modifiers for one trait, preferring persisted admin-managed effects."""
    persisted = []
    if allow_persisted_lookup:
        persisted = _persisted_trait_semantic_modifiers(trait=trait, trait_slug=trait_slug)
    if persisted:
        return persisted

    builder = TRAIT_SEMANTIC_BUILDERS.get(normalize_rule_slug(trait_slug))
    if builder is None:
        return []
    return list(builder(level))
