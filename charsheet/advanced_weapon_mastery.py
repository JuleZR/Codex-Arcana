"""Experience purchases for mastered Waffenmeister characters."""

from django.core.exceptions import ValidationError
from django.db.models import Max
from django.utils import timezone

from charsheet.models import (
    CharacterWeaponMastery,
    CharacterWeaponMasteryArcana,
    Rune,
    WeaponType,
)

PREFIX = "learn_advanced_weapon_"


def configured_options(character):
    from charsheet.learning_progression import (
        weapon_mastery_weapon_type_definitions,
    )

    engine = character.get_engine(refresh=True)
    school_entry = engine._weapon_master_school_entry
    if school_entry is None or school_entry.level != 10:
        return {}
    school = school_entry.school
    owned = engine._weapon_mastery_entries_by_type
    definitions = {
        row["value"]: row["label"]
        for row in weapon_mastery_weapon_type_definitions()
    }
    # Keep legacy selections improvable even without a catalogue item.
    definitions.update({
        slug: entry.weapon_type_label() for slug, entry in owned.items()
    })
    result = {}
    for slug, label in definitions.items():
        entry = owned.get(slug)
        steps = entry.progression_steps(10) if entry else 0
        if steps >= 10:
            continue
        key = f"type_{slug}"
        maneuver, damage = (
            entry.maneuver_damage_bonus(10) if entry else (0, 0)
        )
        result[key] = {
            "key": key,
            "kind": "mastery",
            "school": school,
            "entry": entry,
            "weapon_type": slug,
            "name": label,
            "maneuver": maneuver,
            "damage": damage,
            "first_bonus_kind": (
                entry.first_bonus_kind if entry else "maneuver"
            ),
            "max_steps": 10 - steps,
            "cost": 10,
            "new": entry is None,
        }
    known = {entry.rune_id for entry in engine._weapon_mastery_arcana_entries}
    for rune in Rune.objects.exclude(pk__in=known - {None}).order_by("name"):
        key = f"rune_{rune.pk}"
        result[key] = {
            "key": key,
            "kind": "rune",
            "school": school,
            "rune": rune,
            "name": rune.name,
            "description": rune.description,
            "max_steps": 1,
            "cost": 20,
        }
    return result


def learning_context(character):
    options = list(configured_options(character).values())
    return {
        "learn_advanced_weapon_masteries": [
            option for option in options if option["kind"] == "mastery"
        ],
        "learn_advanced_weapon_runes": [
            option for option in options if option["kind"] == "rune"
        ],
    }


def plan_submission(character, post_data, school_levels):
    options = configured_options(character)
    updates = []
    removals = []
    cost = 0
    for entry in character.weapon_masteries.filter(purchased_steps__gt=0):
        if school_levels.get(str(entry.school_id), 0) < 10:
            removals.append(entry)
            cost -= entry.purchased_steps * 10
    for entry in character.weapon_mastery_arcana_entries.filter(paid_ep__gt=0):
        if school_levels.get(str(entry.school_id), 0) < 10:
            removals.append(entry)
            cost -= entry.paid_ep
    for field in post_data:
        if not str(field).startswith(PREFIX):
            continue
        try:
            count = int(post_data.get(field, 0))
        except (TypeError, ValueError):
            raise ValidationError("Ungültige Waffenmeister-Steigerung.")
        if count == 0:
            continue
        key = str(field).removeprefix(PREFIX)
        option = options.get(key)
        if option is None or not 1 <= count <= option["max_steps"]:
            raise ValidationError(
                "Waffenmeister-Steigerung nicht verfügbar.",
            )
        if school_levels.get(str(option["school"].pk), 0) != 10:
            raise ValidationError("Waffenmeister Stufe 10 ist erforderlich.")
        option = dict(option)
        if option["kind"] == "mastery" and option["new"]:
            side = str(post_data.get(
                f"advanced_weapon_side_{key}", "maneuver",
            ))
            if side not in CharacterWeaponMastery.FirstBonusKind.values:
                raise ValidationError("Ungültiger Startbonus.")
            option["first_bonus_kind"] = side
        updates.append((option, count))
        cost += option["cost"] * count
    return updates, removals, cost


def apply_submission(character, updates, removals):
    for entry in removals:
        if (
            isinstance(entry, CharacterWeaponMastery)
            and entry.pick_order <= 10
        ):
            entry.purchased_steps = 0
            entry.save(update_fields=["purchased_steps"])
        else:
            entry.delete()
    for option, count in updates:
        if option["kind"] == "rune":
            entry = CharacterWeaponMasteryArcana(
                character=character,
                school=option["school"],
                kind=CharacterWeaponMasteryArcana.ArcanaKind.RUNE,
                rune=option["rune"],
                paid_ep=20,
                learned_at=timezone.now(),
            )
        else:
            entry = option["entry"]
            if entry is None:
                last_order = character.weapon_masteries.filter(
                    school=option["school"],
                ).aggregate(last=Max("pick_order"))["last"] or 10
                entry = CharacterWeaponMastery(
                    character=character,
                    school=option["school"],
                    weapon_type=WeaponType.objects.get(
                        slug=option["weapon_type"],
                    ),
                    pick_order=max(10, last_order) + 1,
                    first_bonus_kind=option["first_bonus_kind"],
                    learned_at=timezone.now(),
                )
            entry.purchased_steps += count
        entry.full_clean()
        entry.save()
