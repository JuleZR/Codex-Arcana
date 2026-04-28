"""Learning-menu processing helpers kept outside the view module."""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.db import transaction

from charsheet.learning_progression import build_learning_progression_context
from charsheet.learning_rules import (
    DEFAULT_SCHOOL_MAX_LEVEL,
    calc_attribute_total_cost,
    calc_language_total_cost,
    calc_skill_total_cost,
    school_max_levels,
)
from charsheet.models import (
    Aspect,
    Attribute,
    Character,
    CharacterAttribute,
    CharacterAspect,
    CharacterDivineEntity,
    CharacterLanguage,
    CharacterRaceChoice,
    CharacterSchool,
    CharacterSchoolPath,
    CharacterSpell,
    CharacterSpecialization,
    CharacterSkill,
    CharacterTraitChoice,
    CharacterTrait,
    CharacterTechnique,
    CharacterTechniqueChoice,
    CharacterWeaponMastery,
    CharacterWeaponMasteryArcana,
    Language,
    School,
    Spell,
    Skill,
    Technique,
    Trait,
    TraitChoiceDefinition,
)
from charsheet.constants import is_allowed_trait_attribute_choice


def _read_int(post_data, name: str, default: int = 0) -> int:
    """Read one integer from POST-like data with a safe fallback."""
    try:
        return int(post_data.get(name, str(default)))
    except (TypeError, ValueError):
        return default


class LearningSubmissionError(Exception):
    """Raised when a learning submission cannot be applied safely."""


def _is_checked(post_data, name: str) -> bool:
    """Interpret checkbox-like POST values consistently."""
    return str(post_data.get(name, "")).strip().lower() in {"1", "true", "on", "yes"}


def _has_progression_inputs(post_data) -> bool:
    """Return whether the form contains non-EP progression selections."""
    prefixes = (
        "learn_school_path_",
        "learn_take_technique_",
        "learn_specialization_pick_",
        "learn_weapon_mastery_weapon_",
        "learn_weapon_mastery_side_",
        "learn_weapon_mastery_arcana_",
        "learn_choice_",
        "learn_arcane_free_spell_",
        "learn_bonus_spell_",
        "learn_divine_entity",
    )
    return any(str(key).startswith(prefixes) for key in post_data.keys())


def _apply_progression_choices(character: Character, post_data, *, magic_engine) -> dict[str, int]:
    """Persist zero-cost progression decisions after EP spending has been applied."""
    summary = {
        "paths": 0,
        "techniques": 0,
        "specializations": 0,
        "choices": 0,
    }

    def _rebuild_if(dirty: bool) -> tuple:
        if not dirty:
            return engine, progression_context
        new_engine = character.get_engine(refresh=True)
        return new_engine, build_learning_progression_context(character, engine=new_engine)

    engine = character.get_engine(refresh=True)
    progression_context = build_learning_progression_context(character, engine=engine)

    for row in progression_context["learn_school_path_rows"]:
        raw_path_id = str(post_data.get(row["field_name"], "")).strip()
        if not raw_path_id:
            continue
        allowed_ids = {str(option["id"]) for option in row["options"]}
        if raw_path_id not in allowed_ids:
            raise LearningSubmissionError(f"{row['school_name']}: Ungueltige Pfadauswahl.")
        path_entry = CharacterSchoolPath(
            character=character,
            school_id=row["school_id"],
            path_id=int(raw_path_id),
        )
        path_entry.full_clean()
        path_entry.save()
        summary["paths"] += 1

    engine, progression_context = _rebuild_if(summary["paths"] > 0)

    for row in progression_context["learn_technique_rows"]:
        if not _is_checked(post_data, row["field_name"]):
            continue
        technique_entry = CharacterTechnique(
            character=character,
            technique_id=row["technique_id"],
        )
        technique_entry.full_clean()
        technique_entry.save()
        summary["techniques"] += 1

    engine, progression_context = _rebuild_if(summary["techniques"] > 0)

    for row in progression_context["learn_divine_entity_rows"]:
        raw_entity_id = str(post_data.get(row["field_name"], "")).strip()
        if not raw_entity_id:
            continue
        allowed_ids = {str(option["id"]) for option in row["options"]}
        if raw_entity_id not in allowed_ids:
            raise LearningSubmissionError("Ungueltige Entitaetswahl.")
        entity_binding, _created = CharacterDivineEntity.objects.update_or_create(
            character=character,
            defaults={"entity_id": int(raw_entity_id)},
        )
        entity_binding.full_clean()
        entity_binding.save()
        summary["choices"] += 1

    engine, progression_context = _rebuild_if(summary["choices"] > 0)

    for row in progression_context["learn_arcane_free_spell_rows"]:
        raw_spell_id = str(post_data.get(row["field_name"], "")).strip()
        if not raw_spell_id:
            continue
        allowed_ids = {str(option.id) for option in row["options"]}
        if raw_spell_id not in allowed_ids:
            raise LearningSubmissionError(f"{row['school_name']}: Ungueltige Zauberwahl.")
        spell = Spell.objects.select_related("school", "aspect").filter(pk=int(raw_spell_id)).first()
        if spell is None:
            raise LearningSubmissionError("Zauber nicht gefunden.")
        if spell.school_id and int(spell.grade) > int(row.get("school_level", 0) or 0):
            raise LearningSubmissionError(f"{row['school_name']}: Zauber liegt ueber der aktuellen Stufe.")
        spell_entry = CharacterSpell(
            character=character,
            spell=spell,
            source_kind=CharacterSpell.SourceKind.ARCANE_FREE,
        )
        spell_entry.full_clean()
        spell_entry.save()
        summary["choices"] += 1

    for row in progression_context["learn_bonus_spell_rows"]:
        raw_spell_id = str(post_data.get(row["field_name"], "")).strip()
        if not raw_spell_id:
            continue
        allowed_ids = {str(option.id) for option in row["options"]}
        if raw_spell_id not in allowed_ids:
            raise LearningSubmissionError(f"{row['source_label']}: Ungueltige Bonuszauberwahl.")
        spell = Spell.objects.select_related("school", "aspect").filter(pk=int(raw_spell_id)).first()
        if spell is None:
            raise LearningSubmissionError("Zauber nicht gefunden.")
        if spell.school_id:
            current_level = int(magic_engine._school_level_map().get(spell.school_id, 0))
            if int(spell.grade) > current_level:
                raise LearningSubmissionError(f"{row['source_label']}: Zauber liegt ueber der aktuellen Stufe.")
        elif spell.aspect_id:
            aspect_levels = {
                entry.aspect_id: int(entry.level)
                for entry in magic_engine.get_character_aspects()
            }
            if int(spell.grade) > int(aspect_levels.get(spell.aspect_id, 0)):
                raise LearningSubmissionError(f"{row['source_label']}: Zauber liegt ueber der aktuellen Stufe.")
        source_kind = CharacterSpell.SourceKind.ARCANE_BONUS if spell.school_id else CharacterSpell.SourceKind.DIVINE_BONUS
        spell_entry = CharacterSpell(
            character=character,
            spell=spell,
            source_kind=source_kind,
            bonus_source_id=int(row["bonus_source_id"]),
        )
        spell_entry.full_clean()
        spell_entry.save()
        summary["choices"] += 1

    picked_specializations_by_school: dict[int, set[int]] = {}
    for row in progression_context["learn_specialization_rows"]:
        raw_specialization_id = str(post_data.get(row["field_name"], "")).strip()
        if not raw_specialization_id:
            continue
        allowed_ids = {str(option["id"]) for option in row["options"]}
        if raw_specialization_id not in allowed_ids:
            raise LearningSubmissionError(f"{row['school_name']}: Ungueltige Spezialisierungswahl.")
        school_picks = picked_specializations_by_school.setdefault(row["school_id"], set())
        specialization_id = int(raw_specialization_id)
        if specialization_id in school_picks:
            raise LearningSubmissionError(
                f"{row['school_name']}: Dieselbe Spezialisierung kann nicht mehrfach im selben Schritt gewaehlt werden."
            )
        specialization_entry = CharacterSpecialization(
            character=character,
            specialization_id=specialization_id,
        )
        specialization_entry.full_clean()
        specialization_entry.save()
        school_picks.add(specialization_id)
        summary["specializations"] += 1

    engine, progression_context = _rebuild_if(summary["specializations"] > 0)

    weapon_decisions_by_slot: dict[tuple[int, int], dict[str, object]] = {}
    side_decisions_by_slot: dict[tuple[int, int], dict[str, object]] = {}
    for decision in progression_context["learn_pending_decisions"]:
        kind = decision.get("kind")
        parts = str(decision.get("decision_id") or "").split("-")
        if kind == "weapon_mastery_weapon" and len(parts) >= 5:
            school_id = int(parts[3])
            pick_order = int(parts[4])
            weapon_decisions_by_slot[(school_id, pick_order)] = decision
        elif kind == "weapon_mastery_side" and len(parts) >= 5:
            school_id = int(parts[3])
            pick_order = int(parts[4])
            side_decisions_by_slot[(school_id, pick_order)] = decision

    for slot_key, weapon_decision in weapon_decisions_by_slot.items():
        school_id, pick_order = slot_key
        side_decision = side_decisions_by_slot.get(slot_key)
        if not weapon_decision.get("options") or side_decision is None or not side_decision.get("options"):
            continue
        raw_item_value = str(post_data.get(weapon_decision["options"][0]["submit_name"], "")).strip()
        raw_side_value = str(post_data.get(side_decision["options"][0]["submit_name"], "")).strip()
        if not raw_item_value and not raw_side_value:
            continue
        weapon_allowed_values = {str(option["submit_value"]) for option in weapon_decision["options"]}
        side_allowed_values = {str(option["submit_value"]) for option in side_decision["options"]}
        if raw_item_value not in weapon_allowed_values:
            raise LearningSubmissionError(f"{weapon_decision['title']}: Ungueltige Waffenwahl.")
        if raw_side_value not in side_allowed_values:
            raise LearningSubmissionError(f"{side_decision['title']}: Ungueltige Bonuswahl.")
        mastery_entry = CharacterWeaponMastery(
            character=character,
            school_id=school_id,
            weapon_item_id=int(raw_item_value),
            pick_order=pick_order,
            first_bonus_kind=raw_side_value,
        )
        mastery_entry.full_clean()
        mastery_entry.save()
        summary["choices"] += 1

    engine = character.get_engine(refresh=True)
    progression_context = build_learning_progression_context(character, engine=engine)

    for decision in progression_context["learn_pending_decisions"]:
        if decision.get("kind") != "weapon_mastery_arcana":
            continue
        if not decision.get("options"):
            continue
        raw_value = str(post_data.get(decision["options"][0]["submit_name"], "")).strip()
        if not raw_value:
            continue
        allowed_values = {str(option["submit_value"]) for option in decision["options"]}
        if raw_value not in allowed_values:
            raise LearningSubmissionError(f"{decision['title']}: Ungueltige Arkana-Wahl.")
        school_id = int(str(decision["decision_id"]).split("-")[2])
        payload = {
            "character": character,
            "school_id": school_id,
        }
        if raw_value == CharacterWeaponMasteryArcana.ArcanaKind.BONUS_CAPACITY:
            payload["kind"] = CharacterWeaponMasteryArcana.ArcanaKind.BONUS_CAPACITY
        elif raw_value.startswith("rune:"):
            payload["kind"] = CharacterWeaponMasteryArcana.ArcanaKind.RUNE
            payload["rune_id"] = int(raw_value.split(":", 1)[1])
        else:
            raise LearningSubmissionError(f"{decision['title']}: Ungueltige Arkana-Wahl.")
        arcana_entry = CharacterWeaponMasteryArcana(**payload)
        arcana_entry.full_clean()
        arcana_entry.save()
        summary["choices"] += 1

    # Track (field_name, raw_value) pairs already saved this submission to avoid
    # processing duplicate field names when multiple open slots share the same name.
    saved_field_name_values: set[tuple[str, str]] = set()

    for row in progression_context["learn_choice_rows"]:
        if not row["supported"]:
            continue
        raw_value = str(post_data.get(row["field_name"], "")).strip()
        if not raw_value:
            continue
        dedup_key = (row["field_name"], raw_value)
        if dedup_key in saved_field_name_values:
            continue
        saved_field_name_values.add(dedup_key)

        choice_scope = row.get("choice_scope", "technique")
        choice_label = row.get("technique_name") or row.get("race_name") or row.get("trait_name") or "Choice"
        choice_payload: dict[str, object] = {"character": character}
        choice_model = CharacterTechniqueChoice
        if choice_scope == "race":
            choice_model = CharacterRaceChoice
            choice_payload["definition_id"] = row["definition_id"]
        elif choice_scope == "trait":
            trait_row = CharacterTrait.objects.filter(
                owner=character,
                trait_id=row["trait_id"],
            ).first()
            if trait_row is None:
                raise LearningSubmissionError(f"{choice_label}: Vorteil oder Schwaeche nicht gefunden.")
            choice_model = CharacterTraitChoice
            choice_payload.pop("character", None)
            choice_payload["character_trait"] = trait_row
            choice_payload["definition_id"] = row["definition_id"]
        else:
            choice_payload["technique_id"] = row["technique_id"]
            if row["definition_id"] is not None:
                choice_payload["definition_id"] = row["definition_id"]

        target_kind = row["target_kind"]
        allowed_values = {str(option["value"]) for option in row["options"]}
        if target_kind == TraitChoiceDefinition.TargetKind.ATTRIBUTE:
            if raw_value not in allowed_values:
                raise LearningSubmissionError(f"{choice_label}: Ungueltige Attributswahl.")
            if choice_scope == "trait" and not is_allowed_trait_attribute_choice(row.get("trait_slug"), raw_value):
                raise LearningSubmissionError(f"{choice_label}: Dieses Attribut ist fuer diese Auswahl nicht erlaubt.")
            attribute = Attribute.objects.filter(short_name=raw_value).first()
            if attribute is None:
                raise LearningSubmissionError(f"{choice_label}: Attribut nicht gefunden.")
            choice_payload["selected_attribute"] = attribute
        elif target_kind == TraitChoiceDefinition.TargetKind.RESOURCE:
            if raw_value not in allowed_values:
                raise LearningSubmissionError(f"{choice_label}: Ungueltige Ressourcenwahl.")
            choice_payload["selected_resource"] = raw_value
        elif target_kind == Technique.ChoiceTargetKind.SKILL:
            if raw_value not in allowed_values:
                raise LearningSubmissionError(f"{choice_label}: Ungueltige Fertigkeitswahl.")
            choice_payload["selected_skill_id"] = int(raw_value)
        elif target_kind == Technique.ChoiceTargetKind.SKILL_CATEGORY:
            if raw_value not in allowed_values:
                raise LearningSubmissionError(f"{choice_label}: Ungueltige Kategorienwahl.")
            choice_payload["selected_skill_category_id"] = int(raw_value)
        elif target_kind == Technique.ChoiceTargetKind.ITEM:
            if raw_value not in allowed_values:
                raise LearningSubmissionError(f"{choice_label}: Ungueltige Gegenstandswahl.")
            choice_payload["selected_item_id"] = int(raw_value)
        elif target_kind == Technique.ChoiceTargetKind.ITEM_CATEGORY:
            if raw_value not in allowed_values:
                raise LearningSubmissionError(f"{choice_label}: Ungueltige Gegenstandskategorie.")
            choice_payload["selected_item_category"] = raw_value
        elif target_kind == Technique.ChoiceTargetKind.SPECIALIZATION:
            if raw_value not in allowed_values:
                raise LearningSubmissionError(f"{choice_label}: Ungueltige Spezialisierungswahl.")
            choice_payload["selected_specialization_id"] = int(raw_value)
        elif target_kind == Technique.ChoiceTargetKind.TEXT:
            choice_payload["selected_text"] = raw_value
        else:
            continue

        choice_entry = choice_model(**choice_payload)
        choice_entry.full_clean()
        choice_entry.save()
        summary["choices"] += 1

    return summary


def _reset_invalid_school_progression(character: Character) -> None:
    """Drop school-bound progression data that is no longer valid after level reductions."""
    learned_school_ids = set(character.schools.values_list("school_id", flat=True))
    CharacterSchoolPath.objects.filter(character=character).exclude(
        school_id__in=learned_school_ids
    ).delete()
    CharacterTechniqueChoice.objects.filter(character=character).exclude(
        technique__school_id__in=learned_school_ids
    ).delete()
    CharacterTechnique.objects.filter(character=character).exclude(
        technique__school_id__in=learned_school_ids
    ).delete()

    engine = character.get_engine(refresh=True)
    while True:
        invalid_technique_ids = [
            state["technique_id"]
            for state in engine.technique_states()
            if state["explicitly_learned"]
            and (
                not state["school_known"]
                or not state["required_level_met"]
                or not state["path_allowed"]
                or not state["requirements_met"]
            )
        ]
        if not invalid_technique_ids:
            break
        CharacterTechniqueChoice.objects.filter(
            character=character,
            technique_id__in=invalid_technique_ids,
        ).delete()
        CharacterTechnique.objects.filter(
            character=character,
            technique_id__in=invalid_technique_ids,
        ).delete()
        engine = character.get_engine(refresh=True)

    CharacterSpecialization.objects.filter(character=character).exclude(
        specialization__school_id__in=learned_school_ids
    ).delete()
    CharacterWeaponMastery.objects.filter(character=character).exclude(
        school_id__in=learned_school_ids
    ).delete()
    CharacterWeaponMasteryArcana.objects.filter(character=character).exclude(
        school_id__in=learned_school_ids
    ).delete()
    CharacterSpell.objects.filter(
        character=character,
        spell__school_id__isnull=False,
    ).exclude(
        spell__school_id__in=learned_school_ids
    ).delete()
    magic_engine = character.get_magic_engine(refresh=True)
    school_level_map = magic_engine._school_level_map()
    for school_id in learned_school_ids:
        current_level = school_level_map.get(school_id, 0)
        CharacterSpell.objects.filter(
            character=character,
            spell__school_id=school_id,
            spell__grade__gt=current_level,
        ).delete()
    has_arcane = bool(magic_engine._arcane_school_entries())
    has_divine = CharacterAspect.objects.filter(character=character).exists()
    if not has_arcane and not has_divine:
        CharacterSpell.objects.filter(
            character=character,
            spell__school__isnull=True,
            spell__aspect__isnull=True,
        ).delete()

    engine = character.get_engine(refresh=True)
    for school_id in learned_school_ids:
        allowed_count = engine.specialization_slot_count(school_id)
        specialization_entries = engine.character_specializations(school_id)
        if len(specialization_entries) <= allowed_count:
            continue
        removable_ids = [entry.id for entry in specialization_entries[allowed_count:]]
        CharacterSpecialization.objects.filter(id__in=removable_ids).delete()

    weapon_master_school = School.objects.filter(name__iexact="Waffenmeister").first()
    if weapon_master_school and weapon_master_school.id in learned_school_ids:
        school_entry = CharacterSchool.objects.filter(character=character, school=weapon_master_school).first()
        allowed_count = min(int(getattr(school_entry, "level", 0) or 0), 10)
        CharacterWeaponMastery.objects.filter(
            character=character,
            school=weapon_master_school,
            pick_order__gt=allowed_count,
        ).delete()
        arcana_entries = list(
            CharacterWeaponMasteryArcana.objects.filter(character=character, school=weapon_master_school).order_by("id")
        )
        if len(arcana_entries) > allowed_count:
            CharacterWeaponMasteryArcana.objects.filter(
                id__in=[entry.id for entry in arcana_entries[allowed_count:]]
            ).delete()


def process_learning_submission(character: Character, post_data) -> tuple[str, str]:
    """Apply one learning-menu submission and return message level plus text."""
    magic_engine = character.get_magic_engine(refresh=True)
    magic_engine.sync_character_magic()
    engine = character.get_engine(refresh=True)
    attribute_limits = {
        limit.attribute.short_name: {
            "min": int(limit.min_value),
            "max": int(limit.max_value) + int(engine.resolve_attribute_cap_bonus(limit.attribute.short_name)),
        }
        for limit in character.race.raceattributelimit_set.select_related("attribute")
    }
    attribute_rows = {
        row.attribute.short_name: row
        for row in CharacterAttribute.objects.filter(character=character).select_related("attribute")
    }
    skill_defs = {skill.slug: skill for skill in Skill.objects.all()}
    skill_rows = {
        row.skill.slug: row
        for row in CharacterSkill.objects.filter(character=character).select_related("skill")
    }
    language_defs = {language.slug: language for language in Language.objects.all()}
    language_rows = {
        row.language.slug: row
        for row in CharacterLanguage.objects.filter(owner=character).select_related("language")
    }
    trait_defs = {trait.slug: trait for trait in Trait.objects.all()}
    trait_rows = {
        row.trait.slug: row
        for row in CharacterTrait.objects.filter(owner=character).select_related("trait")
    }
    school_defs = {str(school.id): school for school in School.objects.all()}
    school_rows = {
        str(row.school_id): row
        for row in CharacterSchool.objects.filter(character=character)
    }
    school_level_caps = school_max_levels()

    total_cost = 0
    attr_plan: dict[str, int] = {}
    trait_plan: dict[str, int] = {}
    skill_plan: dict[str, int] = {}
    language_plan: dict[str, dict[str, object]] = {}
    school_plan: dict[str, int] = {}
    magic_spell_plan: set[int] = set()
    magic_aspect_plan: dict[int, int] = {}
    has_progression_inputs = _has_progression_inputs(post_data)

    for short_name, bounds in attribute_limits.items():
        key = f"learn_attr_add_{short_name}"
        if key not in post_data:
            continue
        add = _read_int(post_data, key, 0)
        base_row = attribute_rows.get(short_name)
        base_value = int(base_row.base_value if base_row else 0)
        target_value = base_value + add
        min_value = int(bounds["min"])
        max_value = int(bounds["max"])
        if target_value < min_value:
            return "error", f"{short_name}: Zielwert ist unter dem Minimum."
        if target_value > max_value:
            return "error", f"{short_name}: Zielwert ist ueber dem Maximum."
        if add == 0:
            continue
        step_cost = calc_attribute_total_cost(target_value, max_value) - calc_attribute_total_cost(base_value, max_value)
        total_cost += step_cost
        attr_plan[short_name] = add

    planned_advantages = {
        slug: int(row.trait_level)
        for slug, row in trait_rows.items()
        if row.trait.trait_type == Trait.TraitType.ADV and int(row.trait_level) > 0
    }
    planned_disadvantages = {
        slug: int(row.trait_level)
        for slug, row in trait_rows.items()
        if row.trait.trait_type == Trait.TraitType.DIS and int(row.trait_level) > 0
    }

    for slug, trait in trait_defs.items():
        key = f"learn_trait_add_{slug}"
        if key not in post_data:
            continue
        add = _read_int(post_data, key, 0)
        base_level = int(trait_rows.get(slug).trait_level if slug in trait_rows else 0)
        target_level = base_level + add
        error = engine.validate_trait_target_level(trait, target_level)
        if error:
            return "error", error
        if add == 0:
            continue
        total_cost += engine.trait_learning_delta_cost(trait, base_level, target_level)
        trait_plan[slug] = target_level
        target_map = planned_advantages if trait.trait_type == Trait.TraitType.ADV else planned_disadvantages
        if target_level > 0:
            target_map[slug] = target_level
        else:
            target_map.pop(slug, None)

    advantage_issues = engine.validate_trait_selection(Trait.TraitType.ADV, planned_advantages)
    if advantage_issues:
        return "error", advantage_issues[0]
    disadvantage_issues = engine.validate_trait_selection(Trait.TraitType.DIS, planned_disadvantages)
    if disadvantage_issues:
        return "error", disadvantage_issues[0]
    cross_type_issues = engine.validate_cross_type_trait_selection(planned_advantages, planned_disadvantages)
    if cross_type_issues:
        return "error", cross_type_issues[0]

    for slug, skill in skill_defs.items():
        key = f"learn_skill_add_{slug}"
        if key not in post_data:
            continue
        add = _read_int(post_data, key, 0)
        base_value = int(skill_rows.get(slug).level if slug in skill_rows else 0)
        target_value = base_value + add
        if target_value < 0:
            return "error", f"{skill.name}: Zielwert ist unter 0."
        if target_value > 10:
            return "error", f"{skill.name}: Zielwert ist ueber 10."
        if add == 0:
            continue
        step_cost = calc_skill_total_cost(target_value) - calc_skill_total_cost(base_value)
        total_cost += step_cost
        skill_plan[slug] = add

    cs_skill_plan: dict[int, int] = {}
    cs_skill_rows: dict[int, object] = {}
    for key in list(post_data.keys()):
        if not str(key).startswith("learn_skill_cs_"):
            continue
        try:
            cs_id = int(str(key)[len("learn_skill_cs_"):])
        except ValueError:
            continue
        add = _read_int(post_data, key, 0)
        if add == 0:
            continue
        cs_row = CharacterSkill.objects.filter(id=cs_id, character=character).select_related("skill").first()
        if cs_row is None:
            return "error", "Fertigkeit nicht gefunden."
        base_value = int(cs_row.level)
        target_value = base_value + add
        spec_label = f"{cs_row.skill.name}: {cs_row.specification}"
        if target_value < 0:
            return "error", f"{spec_label}: Zielwert ist unter 0."
        if target_value > 10:
            return "error", f"{spec_label}: Zielwert ist ueber 10."
        step_cost = calc_skill_total_cost(target_value) - calc_skill_total_cost(base_value)
        total_cost += step_cost
        cs_skill_plan[cs_id] = add
        cs_skill_rows[cs_id] = cs_row

    new_spec_plan: list[dict] = []
    new_skill_data: dict[int, dict] = {}
    for key in list(post_data.keys()):
        m = re.match(r"^learn_new_skill_(slug|spec|level)_(\d+)$", str(key))
        if not m:
            continue
        field = m.group(1)
        n = int(m.group(2))
        new_skill_data.setdefault(n, {})[field] = str(post_data.get(key, "")).strip()
    for n, data in sorted(new_skill_data.items()):
        slug = data.get("slug", "")
        spec = data.get("spec", "").strip()
        try:
            level = int(data.get("level", "0") or "0")
        except ValueError:
            level = 0
        if not slug or not spec or level <= 0:
            continue
        skill = skill_defs.get(slug)
        if skill is None:
            return "error", f"Fertigkeit '{slug}' nicht gefunden."
        if not skill.requires_specification:
            return "error", f"{skill.name}: Spezialisierung nicht erlaubt."
        if level > 10:
            return "error", f"{skill.name}: {spec}: Zielwert ist ueber 10."
        if CharacterSkill.objects.filter(character=character, skill=skill, specification=spec).exists():
            return "error", f"{skill.name}: {spec}: Eintrag existiert bereits."
        step_cost = calc_skill_total_cost(level)
        total_cost += step_cost
        new_spec_plan.append({"skill": skill, "spec": spec, "level": level})

    for slug, language in language_defs.items():
        add_key = f"learn_lang_add_{slug}"
        write_key = f"learn_lang_write_{slug}"
        if add_key not in post_data and write_key not in post_data:
            continue
        add = _read_int(post_data, add_key, 0)
        write_add = str(post_data.get(write_key, "0")).lower() in {"1", "true", "on"}
        base_row = language_rows.get(slug)
        base_level = int(base_row.levels if base_row else 0)
        base_write = bool(base_row.can_write if base_row else False)
        base_mother = bool(base_row.is_mother_tongue if base_row else False)
        target_level = base_level + add
        target_write = base_write or write_add
        if base_mother and target_level != int(language.max_level):
            return "error", f"{language.name}: Muttersprache kann nicht unter Maximallevel reduziert werden."
        if target_level < 0:
            return "error", f"{language.name}: Zielwert ist unter 0."
        if target_level > int(language.max_level):
            return "error", f"{language.name}: Zielwert ist ueber dem Maximum."
        if target_write and target_level < 1:
            return "error", f"{language.name}: Schreiben benoetigt mindestens Level 1."
        if add == 0 and not write_add:
            continue
        step_cost = calc_language_total_cost(
            target_level, target_write, base_mother) - calc_language_total_cost(base_level, base_write, base_mother)
        total_cost += step_cost
        language_plan[slug] = {"add": add, "write_add": write_add}

    for school_id, school in school_defs.items():
        key = f"learn_school_add_{school_id}"
        if key not in post_data:
            continue
        add = _read_int(post_data, key, 0)
        base_level = int(school_rows.get(school_id).level if school_id in school_rows else 0)
        target_level = base_level + add
        max_level = max(base_level, int(school_level_caps.get(int(school_id), DEFAULT_SCHOOL_MAX_LEVEL)))
        if target_level < 0:
            return "error", f"{school.name}: Zielwert ist unter 0."
        if target_level > max_level:
            return "error", f"{school.name}: Zielwert ist ueber dem Maximum."
        if add == 0:
            continue
        total_cost += add * 8
        school_plan[school_id] = add

    known_spell_ids = set(CharacterSpell.objects.filter(character=character).values_list("spell_id", flat=True))
    magic_groups = _build_learning_magic_groups(character)
    legal_paid_spell_ids = {
        row["spell_id"]
        for group in magic_groups
        for row in group["rows"]
        if row["kind"] == "magic_spell"
    }
    legal_bonus_aspect_map = {
        row["aspect_id"]: int(row["max_level"])
        for group in magic_groups
        for row in group["rows"]
        if row["kind"] == "magic_aspect"
    }
    for key in post_data.keys():
        if str(key).startswith("learn_magic_spell_"):
            spell_id = _read_int(post_data, key, 0)
            if spell_id < 0:
                spell_id = int(str(key).split("_")[-1])
            else:
                spell_id = int(str(key).split("_")[-1])
            selected = _read_int(post_data, key, 0)
            if selected <= 0:
                continue
            if spell_id in known_spell_ids or spell_id not in legal_paid_spell_ids:
                return "error", "Ungueltige Zusatzzauber-Auswahl."
            total_cost += 2
            magic_spell_plan.add(spell_id)
        elif str(key).startswith("learn_magic_aspect_"):
            aspect_id = int(str(key).split("_")[-1])
            add = _read_int(post_data, key, 0)
            if add <= 0:
                continue
            max_level = int(legal_bonus_aspect_map.get(aspect_id, 0))
            if max_level <= 0 or add > max_level:
                return "error", "Ungueltige Aspekt-Auswahl."
            total_cost += add * 4
            magic_aspect_plan[aspect_id] = add

    has_ep_changes = any((
        attr_plan, trait_plan, skill_plan, cs_skill_plan, new_spec_plan,
        language_plan, school_plan, magic_spell_plan, magic_aspect_plan,
    ))

    if total_cost == 0 and not has_ep_changes and not has_progression_inputs:
        return "info", "Keine Lernkosten erkannt."

    if total_cost > int(character.current_experience):
        return "error", "Nicht genug aktuelle EP fuer diese Lernkosten."

    try:
        with transaction.atomic():
            for short_name, add in attr_plan.items():
                attr_row = attribute_rows.get(short_name)
                if attr_row is None:
                    continue
                attr_row.base_value = int(attr_row.base_value) + add
                attr_row.save(update_fields=["base_value"])

            for slug, target_level in trait_plan.items():
                trait = trait_defs[slug]
                trait_row = trait_rows.get(slug)
                if trait_row is None:
                    if target_level <= 0:
                        continue
                    trait_row = CharacterTrait.objects.create(owner=character, trait=trait, trait_level=target_level)
                    trait_rows[slug] = trait_row
                elif target_level <= 0:
                    trait_row.delete()
                    trait_rows.pop(slug, None)
                else:
                    trait_row.trait_level = target_level
                    trait_row.save(update_fields=["trait_level"])

            for slug, add in skill_plan.items():
                skill = skill_defs[slug]
                skill_row = skill_rows.get(slug)
                if skill_row is None:
                    if add <= 0:
                        continue
                    skill_row = CharacterSkill.objects.create(character=character, skill=skill, level=add)
                    skill_rows[slug] = skill_row
                else:
                    target_level = int(skill_row.level) + add
                    if target_level <= 0:
                        skill_row.delete()
                        skill_rows.pop(slug, None)
                    else:
                        skill_row.level = target_level
                        skill_row.save(update_fields=["level"])

            for cs_id, add in cs_skill_plan.items():
                cs_row = cs_skill_rows[cs_id]
                target_level = int(cs_row.level) + add
                if target_level <= 0:
                    cs_row.delete()
                else:
                    cs_row.level = target_level
                    cs_row.save(update_fields=["level"])

            for entry in new_spec_plan:
                CharacterSkill.objects.create(
                    character=character,
                    skill=entry["skill"],
                    level=entry["level"],
                    specification=entry["spec"],
                )

            for slug, payload in language_plan.items():
                add = int(payload["add"])
                write_add = bool(payload["write_add"])
                language_row = language_rows.get(slug)
                if language_row is None:
                    if add < 1:
                        continue
                    language_row = CharacterLanguage.objects.create(
                        owner=character,
                        language=language_defs[slug],
                        levels=add,
                        can_write=write_add,
                        is_mother_tongue=False,
                    )
                    language_rows[slug] = language_row
                else:
                    target_level = int(language_row.levels) + add
                    target_write = bool(language_row.can_write) or write_add
                    if target_level <= 0 and not target_write and not bool(language_row.is_mother_tongue):
                        language_row.delete()
                        language_rows.pop(slug, None)
                        continue
                    language_row.levels = target_level
                    if write_add:
                        language_row.can_write = True
                    language_row.save(update_fields=["levels", "can_write"])

            for school_id, add in school_plan.items():
                school_row = school_rows.get(school_id)
                if school_row is None:
                    if add <= 0:
                        continue
                    school_row = CharacterSchool.objects.create(
                        character=character,
                        school=school_defs[school_id],
                        level=add,
                    )
                    school_rows[school_id] = school_row
                else:
                    target_level = int(school_row.level) + add
                    if target_level <= 0:
                        school_row.delete()
                        school_rows.pop(school_id, None)
                    else:
                        school_row.level = target_level
                        school_row.save(update_fields=["level"])

            for aspect_id, add in magic_aspect_plan.items():
                aspect = Aspect.objects.filter(pk=aspect_id).first()
                if aspect is None:
                    raise LearningSubmissionError("Aspekt nicht gefunden.")
                aspect_entry = CharacterAspect(
                    character=character,
                    aspect=aspect,
                    level=add,
                    is_bonus_aspect=True,
                )
                aspect_entry.full_clean()
                aspect_entry.save()

            if magic_spell_plan:
                spell_map = {
                    s.id: s for s in Spell.objects.filter(pk__in=magic_spell_plan).select_related("school", "aspect")
                }
                for spell_id in magic_spell_plan:
                    spell = spell_map.get(spell_id)
                    if spell is None:
                        raise LearningSubmissionError("Zauber nicht gefunden.")
                    source_kind = (
                        CharacterSpell.SourceKind.ARCANE_EXTRA if spell.school_id else CharacterSpell.SourceKind.DIVINE_EXTRA
                    )
                    spell_entry = CharacterSpell(
                        character=character,
                        spell=spell,
                        source_kind=source_kind,
                    )
                    spell_entry.full_clean()
                    spell_entry.save()

            magic_engine.sync_character_magic()
            _reset_invalid_school_progression(character)
            character.current_experience = max(0, int(character.current_experience) - total_cost)
            character.save(update_fields=["current_experience"])
            progression_summary = _apply_progression_choices(character, post_data, magic_engine=magic_engine)
    except LearningSubmissionError as exc:
        return "error", str(exc)
    except ValidationError as exc:
        if hasattr(exc, "messages") and exc.messages:
            return "error", " ".join(str(message) for message in exc.messages)
        return "error", str(exc)

    parts: list[str] = []
    if total_cost > 0:
        parts.append(f"{total_cost} EP ausgegeben")
    elif total_cost < 0:
        parts.append(f"{abs(total_cost)} EP erhalten")
    if progression_summary["paths"]:
        parts.append(f"{progression_summary['paths']} Pfadwahl(en) gespeichert")
    if progression_summary["techniques"]:
        parts.append(f"{progression_summary['techniques']} Technik(en) gelernt")
    if progression_summary["specializations"]:
        parts.append(f"{progression_summary['specializations']} Spezialisierung(en) vergeben")
    if progression_summary["choices"]:
        parts.append(f"{progression_summary['choices']} Auswahl(en) gespeichert")
    if magic_aspect_plan:
        parts.append(f"{sum(magic_aspect_plan.values())} Aspektstufe(n) gelernt")
    if magic_spell_plan:
        parts.append(f"{len(magic_spell_plan)} Zauber gelernt")
    if not parts and has_ep_changes:
        parts.append("Aenderungen gespeichert")
    if not parts:
        return "info", "Keine Lernkosten erkannt."
    return "success", f"Lernen abgeschlossen: {', '.join(parts)}."


def _build_learning_magic_groups(character: Character) -> list[dict[str, object]]:
    """Build the same legal magic rows used by the sheet context for learning validation."""
    magic_engine = character.get_magic_engine(refresh=True)
    magic_engine.sync_character_magic()
    known_spell_ids = set(CharacterSpell.objects.filter(character=character).values_list("spell_id", flat=True))
    groups: dict[str, list[dict[str, object]]] = {"Zusatzzauber": [], "Aspekte": []}

    for school_entry in magic_engine._arcane_school_entries():
        choice_state = magic_engine.get_available_arcane_spell_choices(school_entry.school)
        free_choice_ids = {spell.id for spell in choice_state["options"]} if int(choice_state["remaining"]) > 0 else set()
        for spell in Spell.objects.filter(school_id=school_entry.school_id, grade__lte=school_entry.level).exclude(id__in=known_spell_ids):
            if spell.id in free_choice_ids:
                continue
            groups["Zusatzzauber"].append({"kind": "magic_spell", "spell_id": spell.id})

    aspect_levels = {entry.aspect_id: int(entry.level) for entry in magic_engine.get_character_aspects()}
    bonus_aspect_ids = {entry.aspect_id for entry in magic_engine.get_character_aspects() if entry.is_bonus_aspect}
    for spell in Spell.objects.filter(aspect_id__in=aspect_levels.keys()).exclude(id__in=known_spell_ids):
        if int(spell.grade) > int(aspect_levels.get(spell.aspect_id, 0)):
            continue
        if spell.is_base_spell and spell.aspect_id in bonus_aspect_ids:
            continue
        groups["Zusatzzauber"].append({"kind": "magic_spell", "spell_id": spell.id})

    is_magic_user = bool(magic_engine._arcane_school_entries()) or CharacterAspect.objects.filter(character=character).exists()
    if is_magic_user:
        learned_universal_base_ids = set(
            CharacterSpell.objects.filter(
                character=character,
                spell__is_base_spell=True,
                spell__school__isnull=True,
                spell__aspect__isnull=True,
            ).values_list("spell_id", flat=True)
        )
        remaining_base_slots = max(0, 2 - len(learned_universal_base_ids))
        if remaining_base_slots > 0:
            groups["Basiszauber"] = [
                {"kind": "base_spell", "spell_id": spell.id}
                for spell in Spell.objects.filter(is_base_spell=True, school__isnull=True, aspect__isnull=True)
                .exclude(id__in=learned_universal_base_ids)
                .order_by("grade", "name")
            ]

    bonus_aspects = magic_engine.get_available_bonus_aspects()
    for aspect in bonus_aspects["options"]:
        groups["Aspekte"].append(
            {
                "kind": "magic_aspect",
                "aspect_id": aspect.id,
                "max_level": int(bonus_aspects["school_level"]),
            }
        )
    return [{"name": name, "rows": rows} for name, rows in groups.items() if rows]
