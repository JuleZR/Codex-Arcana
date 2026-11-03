"""Owned item inventories and their weight limits."""

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from charsheet.constants import GK_CHOICES
from charsheet.engine.item_engine import ItemEngine
from charsheet.models import CharacterItem


class OwnInventorySettingsForm(forms.Form):
    own_inventory_allowed_size_classes = forms.MultipleChoiceField(
        label="Erlaubte GK", choices=GK_CHOICES, required=False,
        help_text="Leer bedeutet keine Einschränkung.",
    )
    own_inventory_enabled = forms.BooleanField(
        label="Eigene Ablage", required=False,
    )
    own_inventory_capacity_kg = forms.IntegerField(
        label="Traglast (kg)", required=False, min_value=0,
        max_value=2147483647,
        help_text="Leer bedeutet unbegrenzt bei aktivierter Ablage.",
    )
    own_inventory_breaks_at = forms.BooleanField(
        label="Breaks at", required=False,
    )
    own_inventory_breaks_at_kg = forms.IntegerField(
        label="Bruchgrenze (kg)", required=False, min_value=0,
        max_value=2147483647,
    )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("own_inventory_enabled"):
            cleaned.update(
                own_inventory_capacity_kg=None, own_inventory_breaks_at=False,
                own_inventory_breaks_at_kg=None,
                own_inventory_allowed_size_classes=[],
            )
        elif (cleaned.get("own_inventory_breaks_at")
                and cleaned.get("own_inventory_breaks_at_kg") is None):
            self.add_error(
                "own_inventory_breaks_at_kg", "Bitte Bruchgrenze angeben.",
            )
        return cleaned


def apply_inventory_settings(entry, post):
    if "own_inventory_settings" not in post:
        return
    form = OwnInventorySettingsForm(post)
    if not form.is_valid():
        raise ValidationError(form.errors)
    for field, value in form.cleaned_data.items():
        setattr(entry, field, value)


def inventory_settings_payload(entry):
    stat = entry.own_inventory_stat
    return {
        "own_inventory_enabled": bool(stat),
        "own_inventory_allowed_size_classes": (
            stat.allowed_size_classes if stat else []
        ),
        "own_inventory_capacity_kg": stat.capacity_kg if stat else None,
        "own_inventory_breaks_at": stat.breaks_at if stat else False,
        "own_inventory_breaks_at_kg": stat.breaks_at_kg if stat else None,
    }


def _break_inventory(container):
    CharacterItem.objects.filter(pk=container.pk).update(
        inventory_broken=True, equipped=False,
    )
    container.inventory_broken = True
    container.equipped = False
    container.inventory_contents.update(inventory_container=None, stored=False)


def _break_if_overloaded(container, stat):
    if (stat and stat.breaks_at and stat.breaks_at_kg is not None
            and inventory_weight(container) > stat.breaks_at_kg):
        _break_inventory(container)


def inventory_weight(container):
    return sum(
        (ItemEngine(entry).get_weight() for entry in
         container.inventory_contents.select_related("item", "quality")),
        Decimal("0"),
    )


def inventory_allows_size(stat, entry):
    return bool(stat) and (
        not stat.allowed_size_classes
        or ItemEngine(entry).get_size_class() in stat.allowed_size_classes
    )


def reconcile_inventory(entry):
    """Empty unavailable containers and resolve overload after item changes."""
    contents = entry.inventory_contents.all()
    if contents.exists():
        stat = entry.own_inventory_stat
        if (not entry.owner_id or not stat
                or ItemEngine(entry).get_structure_status() == "destroyed"):
            contents.update(inventory_container=None, stored=False)
        else:
            for content in contents.select_related("item"):
                if not inventory_allows_size(stat, content):
                    contents.filter(pk=content.pk).update(
                        inventory_container=None, stored=False,
                    )
            _break_if_overloaded(entry, stat)
        contents.exclude(owner_id=entry.owner_id).update(
            inventory_container=None, stored=False,
        )
    if not entry.inventory_container_id:
        return
    container = entry.inventory_container
    if (entry.owner_id != container.owner_id or entry.equipped or entry.stored
            or not inventory_allows_size(container.own_inventory_stat, entry)):
        CharacterItem.objects.filter(pk=entry.pk).update(
            inventory_container=None,
        )
        entry.inventory_container_id = None
        return
    _break_if_overloaded(container, container.own_inventory_stat)


@transaction.atomic
def move_to_inventory(entry, container_id):
    """Move one complete inventory row, locking this character's inventory."""
    entries = list(CharacterItem.objects.select_for_update().filter(
        owner_id=entry.owner_id,
    ).select_related("item", "quality"))
    container = next((row for row in entries if row.pk == container_id), None)
    if container is None:
        raise ValidationError("Diese Ablage ist nicht verfügbar.")
    stat = container.own_inventory_stat
    from charsheet.item_transfers import item_is_pending

    if (not stat or container.pk == entry.pk or container.amount != 1
            or container.inventory_container_id or entry.equipped
            or entry.equip_locked or item_is_pending(container)
            or item_is_pending(entry)
            or ItemEngine(container).get_structure_status() == "destroyed"
            or entry.own_inventory_stat):
        raise ValidationError(
            "Der Gegenstand kann dort nicht abgelegt werden."
        )
    if not inventory_allows_size(stat, entry):
        raise ValidationError(
            "Diese Größenklasse ist in der Ablage nicht erlaubt."
        )
    weight = sum(
        (ItemEngine(row).get_weight() for row in entries
         if row.inventory_container_id == container.pk and row.pk != entry.pk),
        ItemEngine(entry).get_weight(),
    )
    if (not stat.breaks_at and stat.capacity_kg is not None
            and weight > stat.capacity_kg):
        raise ValidationError("Die Traglast dieser Ablage wird überschritten.")
    entry.inventory_container = container
    entry.stored = False
    entry.save(update_fields=["inventory_container", "stored"])
