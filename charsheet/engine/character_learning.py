"""Learning-related CharacterEngine helpers."""

from __future__ import annotations

from charsheet.modifiers import CharacterBuildValidator, TraitBuildRule
from charsheet.models import Trait


def build_trait_validator(engine, trait_type: str, *, max_disadvantage_cp: int | None = None) -> CharacterBuildValidator:
    """Build a persisted-trait validator for the requested trait family."""
    rules: dict[str, TraitBuildRule] = {}
    for trait in Trait.objects.filter(trait_type=trait_type):
        rules[trait.slug] = TraitBuildRule(
            slug=trait.slug,
            cp_cost=int(trait.points_per_level) if trait_type == Trait.TraitType.ADV else 0,
            cp_refund=int(trait.points_per_level) if trait_type == Trait.TraitType.DIS else 0,
            min_rank=int(trait.min_level),
            max_rank=int(trait.max_level),
            repeatable=int(trait.max_level) > 1,
        )
    cap = int(max_disadvantage_cp) if max_disadvantage_cp is not None else 10**9
    return CharacterBuildValidator(rules=rules, max_disadvantage_cp=cap)


def trait_rank_cost(engine, trait: Trait, level: int) -> int:
    """Return the base rank cost used for post-creation trait retraining."""
    rank = int(level)
    if rank <= 0:
        return 0
    return rank * int(trait.points_per_level)


def validate_trait_target_level(engine, trait: Trait, target_level: int) -> str | None:
    """Validate one post-learning trait level where level 0 means unlearned."""
    level = int(target_level)
    if level < 0:
        return f"{trait.name}: Zielwert ist unter 0."
    if level == 0:
        return None
    if level < int(trait.min_level):
        return f"{trait.name}: Zielwert ist unter dem Minimum."
    if level > int(trait.max_level):
        return f"{trait.name}: Zielwert ist ueber dem Maximum."
    return None


def trait_learning_delta_cost(engine, trait: Trait, base_level: int, target_level: int) -> int:
    """Return the EP cost for changing trait ranks in the learning menu."""
    return abs(int(target_level) - int(base_level)) * int(trait.points_per_level)


def validate_trait_selection(engine, trait_type: str, selected_levels: dict[str, int]) -> list[str]:
    """Validate one final trait selection and return user-facing messages."""
    validator = engine.build_trait_validator(trait_type, max_disadvantage_cp=None)
    issues = validator.validate(selected_levels)
    if not issues:
        return []
    trait_names = {
        trait.slug: trait.name
        for trait in Trait.objects.filter(trait_type=trait_type)
    }
    messages: list[str] = []
    for issue in issues:
        message = str(issue.message)
        for slug, name in trait_names.items():
            message = message.replace(f"'{slug}'", f"'{name}'")
        messages.append(message)
    return messages
