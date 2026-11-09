"""Staff editing of independent catalog definitions."""

import json
from copy import copy, deepcopy

from django import forms
from django.contrib import messages
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.forms import inlineformset_factory
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_http_methods

from charsheet.constants import (
    ATTRIBUTE_CODE_CHOICES, RULE_FLAG_CHOICES, SKILL_COMBAT, STAT_SLUG_CHOICES,
    WEAPON_MANEUVER_DAMAGE, WEAPON_MASTERY_BONUS,
    WEAPON_MASTERY_EFFECT_DESCRIPTION,
)
from charsheet.item_workshop import build_item_effect_previews
from charsheet.models import (
    AlchemicalBrewRequirement, AlchemicalBrewStats, ArmorStats,
    CharacterItem, ConsumableEffectStats, Item, ItemSemanticEffect, ItemType,
    MagicItemStats, Race, RangedWeaponStats, Rune, School, ShieldStats, Skill,
    SkillCategory,
    Specialization, SubstanceStats, WeaponStats, WeaponType, OwnInventoryStat,
)
from charsheet.own_inventory import (
    OwnInventorySettingsForm, reconcile_inventory,
)
from charsheet.sheet_context import (
    _collapse_weapon_mastery_bonus_payloads, _rune_image_url,
    _rune_inline_description,
    _serialize_item_semantic_effect_payload, build_character_item_card_context,
)
from charsheet.shop import (
    _cp_matches_steps, _read_magic_modifier_payloads, _save_magic_modifiers,
)


CATALOG_FIELD_LABELS = {
    "name": "Name", "price": "Preis (KS)", "item_type": "Kategorie",
    "description": "Beschreibung", "subtype": "Unterkategorie",
    "image": "Gegenstandsbild", "stackable": "Stapelbar",
    "hardness": "Härte", "structure_points": "Strukturpunkte",
    "is_consumable": "Verbrauchsgegenstand", "is_magic": "Magisch",
    "magic_effects_without_equipping": "Magische Effekte auch ohne Ausrüsten",
    "rune_effects_without_equipping": "Runeneffekte auch ohne Ausrüsten",
    "not_buyable": "Nicht kaufbar", "not_sellable": "Nicht verkaufbar",
    "invested_cp": "Investierte CP", "invested_cp_steps": "CP-Schritte",
    "default_quality": "Standardqualität", "material": "Material",
    "weight": "Gewicht", "size_class": "Größenklasse",
    "base_values_are_size_adjusted": "Basiswerte bereits an GK angepasst",
    "runes": "Runen", "profile_name": "Profilname",
    "min_st": "Mindeststärke", "min_st_1h": "Mindeststärke (1H)",
    "min_st_2h": "Mindeststärke (2H)", "min_ge_1h": "Mindestgeschick (1H)",
    "min_ge_2h": "Mindestgeschick (2H)", "range_short": "Reichweite: kurz",
    "range_medium": "Reichweite: mittel", "range_long": "Reichweite: weit",
    "range_strength_multiplier": "Reichweite mit Stärke multiplizieren",
    "reload_time": "Nachladezeit", "shot_count": "Schussanzahl",
    "shots": "Schussanzahl", "minimum_strength": "Mindeststärke",
    "damage_source": "Schadensquelle", "damage_label": "Schadensbezeichnung",
    "damage_dice_amount": "Schadenswürfel: Anzahl",
    "damage_dice_faces": "Schadenswürfel: Seiten",
    "damage_flat_bonus": "Schadenszusatz",
    "damage_flat_operator": "Schadensoperator", "damage_type": "Schadenstyp",
    "maneuver_attribute_mode": "Waffenwurf", "weapon_type": "Waffentyp",
    "damage_bonus_attribute": "Attribut für Schadensbonus",
    "damage_bonus_mode": "Berechnung des Schadensbonus",
    "wield_mode": "Waffengriff", "flags": "Waffeneigenschaften",
    "skills": "Fertigkeiten", "h2_dice_amount": "2H: Würfelanzahl",
    "h2_dice_faces": "2H: Würfelseiten", "h2_flat_bonus": "2H: Schadenszusatz",
    "h2_flat_operator": "2H: Schadensoperator",
    "h2_damage_type": "2H: Schadenstyp", "rs_total": "Rüstungsschutz (RS)",
    "rs": "Rüstungsschutz (RS)", "zone_rs_overrides": "RS je Trefferzone",
    "encumbrance": "Belastung", "parade_bonus": "Paradebonus",
    "suppress_component_generation": "Keine Rüstungsteile erzeugen",
    "parent_set": "Übergeordnetes Rüstungsset",
    "component_type": "Rüstungsteil",
    "effect_summary": "Effektbeschreibung", "brew_type": "Gebräuart",
    "ingredient_cost_gm": "Zutatenkosten (GM)",
    "craft_time_amount": "Herstellungsdauer", "craft_time_unit": "Zeiteinheit",
    "craft_mw": "Herstellungs-MW", "craft_ep_cost": "Herstellungskosten (EP)",
    "additional_requirements": "Weitere Voraussetzungen",
    "heal_lp": "LP wiederherstellen", "restore_kp": "KP wiederherstellen",
    "heal_wound_grades": "Wundgrade heilen", "skill": "Fertigkeit",
    "school": "Schule", "aspect": "Aspekt", "required_level": "Stufe",
    "alternative_group": "ODER-Gruppe", "DELETE": "Datensatz entfernen",
    "delivery_method": "Aufnahmeart", "physical_state": "Aggregatzustand",
    "onset": "Wirkungszeit", "duration": "Wirkungsdauer",
    "frequency": "Häufigkeit", "potency": "Potenz",
    "detection_mw": "Erkennungs-MW", "power": "Macht",
    "effect_description": "Wirkung", "dosage_notes": "Dosierung",
    "addiction_notes": "Abhängigkeit", "special_rules": "Sonderregeln",
    "source_reference": "Quelle",
}
for _zone, _label in {
    "head": "Kopf", "face": "Gesicht", "eyes": "Augen", "neck": "Hals",
    "torso": "Torso", "organs": "Organe", "soft_tissue": "Weichteile",
    "arm_left": "Linker Arm", "arm_right": "Rechter Arm",
    "hand_left": "Linke Hand", "hand_right": "Rechte Hand",
    "leg_left": "Linkes Bein", "leg_right": "Rechtes Bein",
    "foot_left": "Linker Fuß", "foot_right": "Rechter Fuß",
}.items():
    CATALOG_FIELD_LABELS[f"covers_{_zone}"] = f"Schützt: {_label}"
for _part, _label in {
    "helmet": "Helm", "arms": "Arme", "legs": "Beine",
    "hands": "Hände", "feet": "Schuhe", "torso": "Torso",
}.items():
    CATALOG_FIELD_LABELS[f"component_price_{_part}_override"] = (
        f"Teilpreis (KS): {_label}"
    )
for _resource, _label in (("heal_lp", "LP"), ("restore_kp", "KP")):
    for _suffix, _detail in (
        ("dice_count", "Würfelanzahl"), ("dice_faces", "Würfelseiten"),
        ("modifier", "Zusatz"), ("divisor", "Teiler"),
    ):
        CATALOG_FIELD_LABELS[f"{_resource}_{_suffix}"] = f"{_label}: {_detail}"


def _catalog_formfield(model_field, **kwargs):
    field = model_field.formfield(**kwargs)
    if field is not None:
        field.label = CATALOG_FIELD_LABELS.get(model_field.name, field.label)
        if isinstance(field, forms.ModelChoiceField):
            field.empty_label = "Bitte wählen" if field.required else "Keine"
        if isinstance(field.widget, forms.Textarea):
            field.widget.attrs.update(rows=3, cols=30)
    return field


class CatalogWeaponStatsForm(forms.ModelForm):
    new_weapon_type = forms.CharField(
        label="Neuen Waffentyp anlegen", required=False, max_length=100,
        help_text=(
            "Ersetzt die Auswahl; wird beim Speichern angelegt."
        ),
    )

    class Meta:
        model = WeaponStats
        fields = "__all__"
        exclude = ("damage_bonus_attribute", "damage_bonus_mode")
        formfield_callback = _catalog_formfield

    def save(self, commit=True):
        instance = super().save(commit=False)
        name = self.cleaned_data.get("new_weapon_type")
        if name:
            weapon_type = WeaponType.objects.filter(name__iexact=name).first()
            if weapon_type is None:
                base_slug = slugify(name)[:50] or "waffentyp"
                slug = base_slug
                suffix = 1
                while WeaponType.objects.filter(slug=slug).exists():
                    ending = f"-{suffix}"
                    slug = base_slug[:50 - len(ending)] + ending
                    suffix += 1
                weapon_type = WeaponType(name=name, slug=slug)
                if commit:
                    weapon_type.save()
            instance.weapon_type = weapon_type
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class CatalogItemForm(forms.ModelForm):
    class Meta:
        model = Item
        exclude = ("catalog_group",)
        formfield_callback = _catalog_formfield

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(deepcopy(OwnInventorySettingsForm.base_fields))
        stat = getattr(self.instance, "owninventorystat", None)
        self.initial.update({
            "own_inventory_enabled": bool(stat),
            "own_inventory_allowed_size_classes": (
                stat.allowed_size_classes if stat else []
            ),
            "own_inventory_capacity_kg": stat.capacity_kg if stat else None,
            "own_inventory_breaks_at": stat.breaks_at if stat else False,
            "own_inventory_breaks_at_kg": stat.breaks_at_kg if stat else None,
        })
        self.fields["item_type"].queryset = ItemType.objects.filter(
            Q(is_active=True) | Q(pk=self.instance.item_type_id),
        )
        for name, widget_id in {
            "name": "runeRetrofitCustomName", "price": "runeRetrofitPrice",
            "weight": "runeRetrofitWeight",
            "size_class": "runeRetrofitSizeClass",
            "default_quality": "runeRetrofitQuality",
            "description": "runeRetrofitDescription",
            "invested_cp": "runeRetrofitInvestedCp",
            "invested_cp_steps": "runeRetrofitInvestedCpSteps",
        }.items():
            self.fields[name].widget.attrs["id"] = widget_id
        self.fields["runes"].widget = forms.MultipleHiddenInput()

    @property
    def primary_fields(self):
        names = (
            "name", "item_type", "price", "default_quality", "weight",
            "size_class", "description",
        )
        if "amount" in self.fields:
            names = ("amount", *names)
        return [self[name] for name in names]

    @property
    def additional_sections(self):
        return [{"title": title, "fields": [self[name] for name in names]}
                for title, names in (
                    ("Material & Widerstand", (
                        "subtype", "material", "hardness", "structure_points",
                        "base_values_are_size_adjusted",
                    )),
                    ("Eigenschaften & Handel", (
                        "stackable", "is_consumable", "is_magic",
                        "magic_effects_without_equipping",
                        "rune_effects_without_equipping",
                        "not_buyable", "not_sellable",
                        *(("remove_catalog_group",)
                          if "remove_catalog_group" in self.fields else ()),
                    )),
                    ("Investierte CP", ("invested_cp", "invested_cp_steps")),
                    ("Gegenstandsbild", ("image",)),
                    ("Eigene Ablage", (
                        "own_inventory_enabled", "own_inventory_capacity_kg",
                        "own_inventory_allowed_size_classes",
                        "own_inventory_breaks_at",
                        "own_inventory_breaks_at_kg",
                    )),
                )]

    def clean_runes(self):
        if "rune_payloads" not in self.data:
            return self.cleaned_data["runes"]
        try:
            payloads = json.loads(self.data.get("rune_payloads") or "[]")
            if not isinstance(payloads, list) or len(payloads) > 5:
                raise ValueError
            ids = {int(entry["rune_id"]) for entry in payloads}
        except (ValueError, TypeError, KeyError) as exc:
            raise ValidationError("Ungültige Runenauswahl.") from exc
        runes = Rune.objects.filter(pk__in=ids)
        if len(ids) != len(payloads) or runes.count() != len(ids):
            raise ValidationError("Bitte jede gültige Rune nur einmal wählen.")
        category = self.cleaned_data.get("item_type")
        if category and any(
            rune.allowed_item_types
            and category.pk not in rune.allowed_item_types
            for rune in runes
        ):
            raise ValidationError(
                "Eine Rune passt nicht zur gewählten Kategorie.",
            )
        return runes

    def clean(self):
        data = super().clean()
        if "own_inventory_settings" in self.data:
            settings_form = OwnInventorySettingsForm(self.data)
            if settings_form.is_valid():
                data.update(settings_form.cleaned_data)
                if (data.get("own_inventory_enabled")
                        and data.get("stackable")):
                    self.add_error(
                        "stackable", "Eigene Ablagen sind nicht stapelbar.",
                    )
            else:
                for field, errors in settings_form.errors.items():
                    for error in errors:
                        self.add_error(field, error)
        if not _cp_matches_steps(
            data.get("invested_cp") or 0, data.get("invested_cp_steps") or "",
        ):
            self.add_error(
                "invested_cp",
                "Investierte CP passen nicht zu den CP-Schritten.",
            )
        return data

    def save(self, commit=True):
        item = super().save(commit=commit)
        if commit and "own_inventory_settings" in self.data:
            if self.cleaned_data.get("own_inventory_enabled"):
                OwnInventoryStat.objects.update_or_create(
                    item=item, defaults={
                        "allowed_size_classes": self.cleaned_data[
                            "own_inventory_allowed_size_classes"],
                        "capacity_kg": self.cleaned_data[
                            "own_inventory_capacity_kg"],
                        "breaks_at": self.cleaned_data[
                            "own_inventory_breaks_at"],
                        "breaks_at_kg": self.cleaned_data[
                            "own_inventory_breaks_at_kg"],
                    },
                )
            else:
                OwnInventoryStat.objects.filter(item=item).delete()
            for entry in CharacterItem.objects.filter(item=item):
                reconcile_inventory(entry)
        return item


# Django supplies all model fields, including M2M and optional profiles.
STAT_SECTIONS = (
    (WeaponStats, "Waffenprofile", "supports_weapon_stats"),
    (RangedWeaponStats, "Fernkampfwerte", "supports_weapon_stats"),
    (ArmorStats, "Rüstungswerte", "supports_armor_stats"),
    (ShieldStats, "Schildwerte", "supports_shield_stats"),
    (SubstanceStats, "Substanzwerte", "supports_substance_stats"),
    (ConsumableEffectStats, "Verbrauchseffekte", "is_consumable"),
    (AlchemicalBrewStats, "Alchemistische Werte", "supports_alchemical_stats"),
    (MagicItemStats, "Magische Beschreibung", "magic"),
)


def _require_staff_permission(user, action):
    if not user.is_staff or not user.has_perm(f"charsheet.{action}_item"):
        raise PermissionDenied


def _stat_formsets(item, data=None, files=None):
    sections = []
    for model, label, capability in STAT_SECTIONS:
        factory = inlineformset_factory(
            Item, model, fields="__all__", extra=1, can_delete=True,
            form=(CatalogWeaponStatsForm if model is WeaponStats
                  else forms.ModelForm),
            formfield_callback=_catalog_formfield,
        )
        formset = factory(
            data=data, files=files, instance=item,
            prefix=model._meta.model_name,
        )
        formset.catalog_empty_form = formset.empty_form
        # Armor components may only refer to independent catalog definitions.
        for form in [*formset.forms, formset.catalog_empty_form]:
            form.fields["DELETE"].label = "Datensatz entfernen"
            if model is WeaponStats:
                form.fields["skills"].queryset = Skill.objects.filter(
                    category__slug=SKILL_COMBAT,
                ).order_by("name")
                for name in ("flags", "skills"):
                    field = form.fields[name]
                    field.widget = FilteredSelectMultiple(
                        field.label, is_stacked=False,
                        choices=field.choices,
                    )
                for prefix in ("damage_", "h2_"):
                    for suffix, field_label in (
                        ("dice_amount", "Würfel"), ("dice_faces", "W"),
                        ("flat_operator", "Operator"), ("flat_bonus", "Bonus"),
                        ("damage_type" if prefix == "h2_" else "type",
                         "Schadenstyp"),
                    ):
                        form.fields[f"{prefix}{suffix}"].label = field_label
                form.weapon_sections = [
                    {"title": title, "layout": layout,
                     "fields": [form[name] for name in names.split()]}
                    for title, layout, names in (
                        ("Profil", "profile",
                         "profile_name weapon_type new_weapon_type wield_mode "
                         "maneuver_attribute_mode"),
                        ("Voraussetzungen", "requirements",
                         "min_st min_st_1h min_st_2h min_ge_1h min_ge_2h"),
                        ("Schaden", "damage",
                         "damage_source damage_dice_amount "
                         "damage_dice_faces damage_flat_operator "
                         "damage_flat_bonus damage_type"),
                        ("Zweihandschaden", "two-handed",
                         "h2_dice_amount h2_dice_faces h2_flat_operator "
                         "h2_flat_bonus h2_damage_type"),
                        ("Reichweite & Schussfolge", "range",
                         "range_short range_medium range_long "
                         "range_strength_multiplier reload_time shot_count"),
                        ("Eigenschaften & Fertigkeiten", "assignments",
                         "flags skills"),
                    )
                ]
                form.weapon_management_fields = [
                    *form.hidden_fields(), form["DELETE"],
                ]
            if model is RangedWeaponStats:
                form.fields["skills"].queryset = Skill.objects.filter(
                    category__slug=SKILL_COMBAT,
                ).order_by("name")
                for name in ("flags", "skills"):
                    field = form.fields[name]
                    field.widget = FilteredSelectMultiple(
                        field.label, is_stacked=False, choices=field.choices,
                    )
                for name, label in (
                    ("damage_dice_amount", "Würfel"),
                    ("damage_dice_faces", "W"),
                    ("damage_flat_operator", "Operator"),
                    ("damage_flat_bonus", "Bonus"),
                ):
                    form.fields[name].label = label
                form.weapon_sections = [
                    {"title": title, "layout": layout,
                     "fields": [form[name] for name in names.split()]}
                    for title, layout, names in (
                        ("Profil", "profile",
                         "weapon_type maneuver_attribute_mode"),
                        ("Voraussetzungen", "requirements",
                         "minimum_strength"),
                        ("Schaden", "damage",
                         "damage_label damage_dice_amount damage_dice_faces "
                         "damage_flat_operator damage_flat_bonus damage_type"),
                        ("Reichweite & Schussfolge", "range",
                         "range_short range_medium range_long "
                         "range_strength_multiplier reload_time shots"),
                        ("Eigenschaften & Fertigkeiten", "assignments",
                         "flags skills"),
                    )
                ]
                form.weapon_management_fields = [
                    *form.hidden_fields(), form["DELETE"],
                ]
            if "parent_set" in form.fields:
                form.fields["parent_set"].queryset = ArmorStats.objects.filter(
                    item__catalog_group__isnull=True,
                )
        sections.append({
            "label": label, "capability": capability, "formset": formset,
        })
    return sections


def _effect_context(payloads):
    context = {
        "magic_editor_payloads": payloads,
        "magic_editor_effect_kinds": [
            ("text", "Nur Beschreibung"), ("rule_flag", "Regel aktivieren"),
            ("school_level", "Erlernte Schulstufen"),
            ("school_level_grant", "Schulstufen"),
            ("attribute", "Attribut"), ("stat", "Abgeleiteter Wert"),
            ("combat", "Kampf / Waffe"),
            ("wound_stage", "Wundstufe einfügen"),
            ("artefact_rank", "Artefaktrang"),
            ("additional_arcane_power", "Zusätzlicher KP-Vorrat"),
            ("skill", "Einzelne Fertigkeit"),
            ("category", "Fertigkeitskategorie"),
            ("weapon_maneuver", "Bonus/Malus auf Manöver"),
            ("weapon_damage", "Bonus/Malus auf Schaden"),
            ("weapon_damage_dice", "Zusätzliche Schadenswürfel"),
            (WEAPON_MANEUVER_DAMAGE, "Bonus/Malus auf Manöver und Schaden"),
            (WEAPON_MASTERY_BONUS, WEAPON_MASTERY_EFFECT_DESCRIPTION),
            ("movement", "Bewegung"),
            ("specialization", "Spezialisierung"),
        ],
        "magic_editor_attribute_choices": ATTRIBUTE_CODE_CHOICES,
        "magic_editor_stat_choices": STAT_SLUG_CHOICES,
        "magic_editor_rule_choices": RULE_FLAG_CHOICES,
        "magic_editor_movement_choices": [
            (f"{mode}{suffix}", f"{label}{detail}")
            for mode, label in (
                ("ground", "Laufen"), ("swim", "Schwimmen"),
                ("fly", "Fliegen"),
            )
            for suffix, detail in (
                ("", ": alle Werte"), ("_combat", " Kampf"),
                ("_march", " Marsch"), ("_sprint", " Sprint"),
            )
        ],
        "magic_editor_skill_choices": Skill.objects.order_by("name"),
        "magic_editor_category_choices": (
            SkillCategory.objects.order_by("name")
        ),
        "magic_editor_item_choices": Item.objects.filter(
            catalog_group__isnull=True,
        ).order_by("name"),
        "magic_editor_item_category_choices": Item.type_choices(),
        "magic_editor_specialization_choices": (
            Specialization.objects.order_by("name")
        ),
        "magic_editor_race_choices": Race.objects.order_by("name"),
        "magic_editor_school_choices": School.objects.order_by("name"),
    }
    # Inputs consumed by the character sheet's inline workshop.
    for suffix, source in {
        "attribute": "attribute", "stat": "stat", "movement": "movement",
        "rule_flag": "rule", "skill": "skill",
        "skill_category": "category", "item": "item",
        "item_category": "item_category", "specialization": "specialization",
        "race": "race", "school": "school",
    }.items():
        context[f"shop_modifier_{suffix}_choices"] = context[
            f"magic_editor_{source}_choices"
        ]
    context["item_modifier_target_kind_choices"] = context[
        "magic_editor_effect_kinds"
    ]
    context["rune_retrofit_choices"] = [{
        "id": rune.pk, "name": rune.name,
        "description": _rune_inline_description(rune),
        "image": _rune_image_url(rune), "allow_multiple": False,
        "allowed_item_types": rune.allowed_item_types,
        "has_specialization": False, "is_level_scaled": False,
    } for rune in Rune.objects.order_by("name")]
    return context


class _PreviewRows(list):
    """In-memory related rows for the normal card renderer; never saved."""

    def all(self):
        return self

    def order_by(self, *fields):
        rows = self
        for field in reversed(fields):
            rows = sorted(
                rows, key=lambda row: getattr(row, field.lstrip("-")),
                reverse=field.startswith("-"),
            )
        return _PreviewRows(rows)

    def select_related(self, *fields):
        return self

    def exists(self):
        return bool(self)

    def first(self):
        return self[0] if self else None


def _catalog_card_preview(item, post, effects, viewer):
    """Render the real card from unsaved catalog and stat drafts."""
    data = post.copy()
    data["name"] = data.get("name") or "Neuer Gegenstand"
    draft = copy(item)
    form = CatalogItemForm(data, instance=draft)
    if not form.is_valid():
        raise ValidationError("Bitte die Grunddaten für die Vorschau prüfen.")
    sections = _stat_formsets(draft, data)
    if not all([section["formset"].is_valid() for section in sections]):
        raise ValidationError("Bitte die Werte für die Vorschau prüfen.")
    draft._prefetched_objects_cache = {"runes": form.cleaned_data["runes"]}
    for section in sections:
        formset = section["formset"]
        rows = _PreviewRows()
        for entry in formset.forms:
            if entry.cleaned_data.get("DELETE") or not entry.cleaned_data:
                continue
            if not entry.instance.pk and not entry.has_changed():
                continue
            row = entry.save(commit=False)
            row._prefetched_objects_cache = {
                field.name: entry.cleaned_data[field.name]
                for field in row._meta.many_to_many
                if field.name in entry.cleaned_data
            }
            rows.append(row)
        relation = formset.model._meta.get_field("item")
        accessor = relation.remote_field.get_accessor_name()
        if relation.one_to_one:
            setattr(draft, accessor, rows.first())
        else:
            draft._prefetched_objects_cache[accessor] = rows
        for index, row in enumerate(rows):
            if not row.pk:
                row.pk = -(index + 1)
    brew = getattr(draft, "alchemicalbrewstats", None)
    draft._card_draft_brew = brew
    if brew is not None:
        factory = inlineformset_factory(
            AlchemicalBrewStats, AlchemicalBrewRequirement,
            fields="__all__", extra=1, can_delete=True,
            formfield_callback=_catalog_formfield,
        )
        requirements = factory(
            data=data, instance=brew, prefix="brew_requirements",
        )
        if not requirements.is_valid():
            raise ValidationError("Bitte die Voraussetzungen prüfen.")
        brew._prefetched_objects_cache["requirements"] = _PreviewRows(
            entry.save(commit=False) for entry in requirements.forms
            if entry.cleaned_data and not entry.cleaned_data.get("DELETE")
            and (entry.instance.pk or entry.has_changed())
        )
        for index, requirement in enumerate(
            brew._prefetched_objects_cache["requirements"],
        ):
            requirement.pk = requirement.pk or -(index + 1)
    # Negative IDs only allow read-only related managers on these unsaved
    # objects. No Item or CharacterItem instance is written to the database.
    draft.pk = draft.pk or -1
    owned = CharacterItem(
        pk=-1, item=draft, quality=draft.default_quality,
        description=draft.description or "", invested_cp=draft.invested_cp,
        is_magic=draft.is_magic_effective,
    )
    owned._prefetched_objects_cache = {
        "runes": form.cleaned_data["runes"], "item_runes": _PreviewRows(),
        "rune_specs": _PreviewRows(),
    }
    card = build_character_item_card_context(
        owned, viewer, preview_player=False, modifier_payloads=effects,
    )
    return render_to_string(
        "charsheet/partials/_shared_item_card.html", {"item_card": card},
    )


@login_required
@require_GET
def staff_items(request):
    if not (request.user.is_staff and (
        request.user.has_perm("charsheet.change_item")
        or request.user.has_perm("charsheet.add_item")
    )):
        raise PermissionDenied
    items = Item.objects.filter(catalog_group__isnull=True).select_related(
        "item_type", "default_quality",
    ).order_by("name", "pk")
    if not request.user.has_perm("charsheet.change_item"):
        items = items.none()
    query = str(request.GET.get("q") or "").strip()
    if query:
        items = items.filter(name__icontains=query)
    category = str(request.GET.get("category") or "")
    if category:
        items = items.filter(item_type_id=category)
    page = Paginator(items, 30).get_page(request.GET.get("page"))
    return render(request, "charsheet/staff_items.html", {
        "items": page.object_list, "query": query, "page_obj": page,
        "item_types": ItemType.objects.order_by("form_sort_order", "name"),
        "category": category, "embedded": request.GET.get("embedded") == "1",
    })


@login_required
@require_http_methods(["GET", "POST"])
def staff_item_editor(request, item_id=None):
    _require_staff_permission(request.user, "change" if item_id else "add")
    return catalog_item_editor(request, item_id=item_id)


def catalog_item_editor(request, item_id=None, group=None):
    """Shared workshop; callers authorize staff or group access."""
    item = get_object_or_404(
        Item, pk=item_id, catalog_group=group,
    ) if item_id else Item(item_type=(
        ItemType.objects.filter(pk="misc", is_active=True).first()
        or ItemType.objects.filter(is_active=True).first()
    ), catalog_group=group)
    if request.method == "POST" and request.GET.get("preview") == "1":
        try:
            previews, effects = build_item_effect_previews(request.POST)
            result = {"previews": previews}
            if request.POST.get("include_item_card"):
                result["item_card_html"] = _catalog_card_preview(
                    item, request.POST, effects, request.user,
                )
        except (ValidationError, ValueError, TypeError):
            return JsonResponse({"error": "Ungültige Effekte."}, status=400)
        return JsonResponse(result)
    data = request.POST if request.method == "POST" else None
    files = request.FILES if data is not None else None
    form = CatalogItemForm(data, files, instance=item)
    if group is not None and item_id is None:
        form.fields["amount"] = forms.IntegerField(
            label="Instanzmenge", min_value=1, initial=1,
        )
    elif group is not None:
        form.fields["remove_catalog_group"] = forms.BooleanField(
            label="Aus Gruppenkatalog lösen", required=False,
        )
    sections = _stat_formsets(item, data, files)
    brew = (
        AlchemicalBrewStats.objects.filter(item=item).first()
        if item.pk else None
    )
    requirement_factory = inlineformset_factory(
        AlchemicalBrewStats, AlchemicalBrewRequirement,
        fields="__all__", extra=1, can_delete=True,
        formfield_callback=_catalog_formfield,
    )
    requirements = requirement_factory(
        data=data, instance=brew or AlchemicalBrewStats(item=item),
        prefix="brew_requirements",
    )
    for requirement in requirements.forms:
        requirement.fields["DELETE"].label = "Voraussetzung entfernen"
    payloads = json.dumps(_collapse_weapon_mastery_bonus_payloads([
        _serialize_item_semantic_effect_payload(effect)
        for effect in ItemSemanticEffect.objects.filter(item=item).order_by(
            "sort_order", "id",
        ).prefetch_related("condition_races", "condition_schools")
    ])) if item.pk else "[]"
    if data is not None:
        payloads = data.get("magic_modifier_payloads", "[]")
        valid = form.is_valid()
        if valid:
            # The base form has now populated the same parent instance used by
            # all inline forms, including its category and capability flags.
            valid = all([
                section["formset"].is_valid() for section in sections
            ])
            valid = requirements.is_valid() and valid
        try:
            raw_effects = json.loads(payloads)
            if not isinstance(raw_effects, list) or len(raw_effects) > 100:
                raise ValidationError("Ungültige Effekte.")
            effects = _read_magic_modifier_payloads(data)
            if valid and effects and not item.is_magic_effective:
                raise ValidationError(
                    "Für Effekte bitte das Item als magisch markieren.",
                )
            if valid:
                with transaction.atomic():
                    if form.cleaned_data.get("remove_catalog_group"):
                        item.catalog_group = None
                        item.validate_unique()
                        item.validate_constraints()
                    item = form.save()
                    for section in sections:
                        section["formset"].save()
                    brew = AlchemicalBrewStats.objects.filter(
                        item=item,
                    ).first()
                    if any(
                        entry.has_changed()
                        and not entry.cleaned_data.get("DELETE")
                        for entry in requirements.forms
                    ) and brew is None:
                        raise ValidationError(
                            "Voraussetzungen benötigen alchemistische Werte.",
                        )
                    if brew is not None:
                        requirements.instance = brew
                        requirements.save()
                    _save_magic_modifiers(
                        source_model=Item, source_id=item.pk,
                        magic_modifier_payloads=effects,
                    )
                    if group is not None and item_id is None:
                        instance = CharacterItem(
                            item=item, group_owner=group,
                            original_owner_group=group,
                            amount=(form.cleaned_data["amount"]
                                    if item.stackable else 1),
                            quality=item.default_quality,
                        )
                        instance.full_clean()
                        instance.save()
                if group is not None:
                    messages.success(
                        request,
                        "Basisitem-Stammdaten gespeichert." if item_id else
                        "Gruppenprivates Basisitem und Instanz angelegt.",
                    )
                    if request.GET.get("embedded") == "1":
                        return render(
                            request, "charsheet/catalog_item_saved.html", {
                                "return_url": reverse(
                                    "game_master_screen", args=[group.pk],
                                ) + "#sl-inventar",
                            },
                        )
                    return redirect(
                        reverse("game_master_screen", args=[group.pk])
                        + "#sl-inventar",
                    )
                messages.success(request, "Item gespeichert.")
                if request.user.has_perm("charsheet.change_item"):
                    url = reverse("staff_item_edit", args=[item.pk])
                    if request.GET.get("embedded") == "1":
                        url += "?embedded=1"
                    return redirect(url)
                if request.GET.get("embedded") == "1":
                    return redirect(
                        reverse("staff_item_create") + "?embedded=1",
                    )
                return redirect("dashboard")
        except (ValidationError, ValueError, TypeError) as exc:
            form.add_error(None, " ".join(exc.messages) if isinstance(
                exc, ValidationError,
            ) else "Ungültige Effekte.")
        except IntegrityError:
            form.add_error(
                None, "Ein Item mit diesem Namen existiert bereits.",
            )
    return render(request, "charsheet/staff_item_editor.html", {
        "item": item, "form": form, "stat_sections": sections,
        "catalog_group": group,
        "requirements": requirements, **_effect_context(payloads),
        "embedded": request.GET.get("embedded") == "1",
        "catalog_rune_payloads": (
            data.get("rune_payloads") if data is not None
            and "rune_payloads" in data else json.dumps([
                {"rune_id": int(pk)} for pk in form["runes"].value() or []
            ])
        ),
    }, status=400 if data is not None else 200)
