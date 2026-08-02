"""Shared vampire rules without a cross-domain actor abstraction."""

from __future__ import annotations

from dataclasses import dataclass
from random import SystemRandom
from typing import Any, Iterable

from django.core.exceptions import ValidationError
from django.db import transaction

from charsheet.constants import (
    ATTR_WILL,
    SCHOOL_ARCANE,
    SCHOOL_COMBAT,
    VAMPIRE_MODE_DISABLE,
    VAMPIRE_MODE_ENABLE,
    VAMPIRE_REGENERATION,
    VAMPIRE_STRENGTH_OVER_RACE_MAXIMUM,
    VAMPIRE_STATE_ACTIVE,
    VAMPIRE_STATE_DESTROYED,
    VAMPIRE_STATE_TORPOR,
)
from charsheet.models.character import Character
from charsheet.models.creatures import CharacterCreature, Creature
from charsheet.models.groups import GameGroupCreature
from charsheet.models.vampirism import (
    CharacterVampirePower,
    CharacterVampireTrait,
    VampirePower,
    VampireTrait,
    VampireTraitSemanticEffect,
    VampireTraitOverrideMode,
)


DAILY_BLOOD_COST = 2
POWER_KILL_WINDOW_DAYS = 28
AGE_CYCLE_COST = 10
BLOOD_CAPACITY_POINT_COST = 3
VAMPIRE_TRAIT_COST = 5
VAMPIRE_POWER_COST = 15
VAMPIRE_POWER_WITHOUT_WEAKNESS_COST = 20
VAMPIRE_WEAKNESS_REMOVAL_COST = 5
REGENERATION_COST = 2
HARD_REGENERATION_COST = 8


class VampireRuleError(ValidationError):
    """Raised when a strict vampire action would violate a documented rule."""


@dataclass(frozen=True)
class EffectiveVampireTrait:
    trait: VampireTrait
    source: str = ""

    @property
    def rank(self) -> int:
        return 1


@dataclass(frozen=True)
class EffectiveVampirePower:
    power: VampirePower
    level: int = 1
    purchased_without_weakness: bool = False
    weakness_bought_off: bool = False
    source: str = ""

    @property
    def rank(self) -> int:
        return max(1, int(self.level or 1))

    @property
    def weakness_is_active(self) -> bool:
        return not self.purchased_without_weakness and not self.weakness_bought_off


@dataclass(frozen=True)
class VampireResourceState:
    intelligent: int
    animal: int
    maximum: int
    potential: int

    @property
    def total(self) -> int:
        return self.intelligent + self.animal


class VampireRules:
    """Resolve and mutate vampire state for one supported concrete domain object."""

    supported_types = (Character, Creature, CharacterCreature, GameGroupCreature)

    def __init__(self, actor: Character | Creature | CharacterCreature | GameGroupCreature):
        if not isinstance(actor, self.supported_types):
            raise TypeError(f"Nicht unterstützte Vampir-Domäne: {type(actor)!r}")
        self.actor = actor

    @staticmethod
    def trait_point_delta(trait: VampireTrait) -> int:
        """Return the fixed CP/EP delta for a fundamental vampire trait."""
        if trait.trait_type == VampireTrait.TraitType.ADVANTAGE:
            return VAMPIRE_TRAIT_COST
        if trait.trait_type == VampireTrait.TraitType.DISADVANTAGE:
            return -VAMPIRE_TRAIT_COST
        return 0

    @staticmethod
    def power_cost(*, without_weakness: bool = False) -> int:
        return VAMPIRE_POWER_WITHOUT_WEAKNESS_COST if without_weakness else VAMPIRE_POWER_COST

    @staticmethod
    def age_cycle_cost(age_cycle: int) -> int:
        return max(0, int(age_cycle or 1) - 1) * AGE_CYCLE_COST

    @staticmethod
    def capacity_bonus_cost(points: int) -> int:
        return max(0, int(points or 0)) * BLOOD_CAPACITY_POINT_COST

    @property
    def is_template(self) -> bool:
        return isinstance(self.actor, Creature)

    def is_vampire(self) -> bool:
        actor = self.actor
        if isinstance(actor, Character):
            return actor.is_vampire
        if isinstance(actor, Creature):
            return bool(actor.vampire_default_enabled)
        if actor.vampire_mode == VAMPIRE_MODE_ENABLE:
            return True
        if actor.vampire_mode == VAMPIRE_MODE_DISABLE:
            return False
        if isinstance(actor, CharacterCreature):
            return bool(actor.creature_id and actor.creature.vampire_default_enabled)
        if actor.character_creature_id:
            return VampireRules(actor.character_creature).is_vampire()
        return bool(actor.creature_id and actor.creature.vampire_default_enabled)

    def age_cycle(self) -> int:
        actor = self.actor
        if isinstance(actor, Character):
            base = max(1, int(actor.vampire_age_cycle or 1))
            return base + int(actor.vampire_sacrament_age_bonus or 0)
        if isinstance(actor, Creature):
            return max(1, int(actor.vampire_age_cycle_default or 1))
        if isinstance(actor, CharacterCreature):
            if actor.vampire_age_cycle_override is not None:
                base = max(1, int(actor.vampire_age_cycle_override))
            elif actor.creature_id:
                base = max(1, int(actor.creature.vampire_age_cycle_default or 1))
            else:
                base = 1
            return base + int(actor.vampire_sacrament_age_bonus or 0)
        base = max(1, int(actor.vampire_age_cycle or 1))
        return base + int(actor.vampire_sacrament_age_bonus or 0)

    @staticmethod
    def _apply_trait_overrides(
        base: dict[int, EffectiveVampireTrait], rows: Iterable[Any], source: str
    ) -> dict[int, EffectiveVampireTrait]:
        resolved = dict(base)
        for row in rows:
            if row.mode == VampireTraitOverrideMode.REMOVE:
                resolved.pop(row.trait_id, None)
            else:
                resolved[row.trait_id] = EffectiveVampireTrait(trait=row.trait, source=source)
        return resolved

    @staticmethod
    def _apply_power_overrides(
        base: dict[int, EffectiveVampirePower], rows: Iterable[Any], source: str
    ) -> dict[int, EffectiveVampirePower]:
        resolved = dict(base)
        for row in rows:
            if row.mode == VampireTraitOverrideMode.REMOVE:
                resolved.pop(row.power_id, None)
                continue
            inherited = resolved.get(row.power_id)
            without_weakness = (
                row.purchased_without_weakness
                if row.purchased_without_weakness is not None
                else inherited.purchased_without_weakness
                if inherited
                else False
            )
            bought_off = (
                row.weakness_bought_off
                if row.weakness_bought_off is not None
                else inherited.weakness_bought_off
                if inherited
                else False
            )
            level = (
                row.level
                if row.level is not None
                else inherited.level
                if inherited
                else 1
            )
            resolved[row.power_id] = EffectiveVampirePower(
                power=row.power,
                level=max(1, int(level or 1)),
                purchased_without_weakness=bool(without_weakness),
                weakness_bought_off=bool(bought_off),
                source=source,
            )
        return resolved

    def _trait_definition_rows(self) -> dict[int, EffectiveVampireTrait]:
        actor = self.actor
        if isinstance(actor, Character):
            return {
                row.trait_id: EffectiveVampireTrait(trait=row.trait, source="character")
                for row in actor.vampire_trait_ownerships.select_related("trait").prefetch_related(
                    "trait__semantic_effects"
                )
            }
        if isinstance(actor, Creature):
            return {
                row.trait_id: EffectiveVampireTrait(trait=row.trait, source="template")
                for row in actor.vampire_trait_defaults.select_related("trait").prefetch_related(
                    "trait__semantic_effects"
                )
            }
        if isinstance(actor, CharacterCreature):
            base = VampireRules(actor.creature)._trait_definition_rows() if actor.creature_id else {}
            rows = actor.vampire_trait_overrides.select_related("trait").prefetch_related(
                "trait__semantic_effects"
            )
            return self._apply_trait_overrides(base, rows, "instance")
        if actor.vampire_mode == VAMPIRE_MODE_ENABLE:
            base = {}
        elif actor.character_creature_id:
            base = VampireRules(actor.character_creature)._trait_definition_rows()
        elif actor.creature_id:
            base = VampireRules(actor.creature)._trait_definition_rows()
        else:
            base = {}
        rows = actor.vampire_trait_overrides.select_related("trait").prefetch_related(
            "trait__semantic_effects"
        )
        return self._apply_trait_overrides(base, rows, "gm")

    def _power_definition_rows(self) -> dict[int, EffectiveVampirePower]:
        actor = self.actor
        if isinstance(actor, Character):
            return {
                row.power_id: EffectiveVampirePower(
                    power=row.power,
                    level=max(1, int(row.level or 1)),
                    purchased_without_weakness=bool(row.purchased_without_weakness),
                    weakness_bought_off=bool(row.weakness_bought_off),
                    source="character",
                )
                for row in actor.vampire_power_ownerships.select_related("power").prefetch_related(
                    "power__semantic_effects"
                )
            }
        if isinstance(actor, Creature):
            return {
                row.power_id: EffectiveVampirePower(
                    power=row.power,
                    level=max(1, int(row.level or 1)),
                    purchased_without_weakness=bool(row.purchased_without_weakness),
                    weakness_bought_off=bool(row.weakness_bought_off),
                    source="template",
                )
                for row in actor.vampire_power_defaults.select_related("power").prefetch_related(
                    "power__semantic_effects"
                )
            }
        if isinstance(actor, CharacterCreature):
            base = VampireRules(actor.creature)._power_definition_rows() if actor.creature_id else {}
            rows = actor.vampire_power_overrides.select_related("power").prefetch_related(
                "power__semantic_effects"
            )
            return self._apply_power_overrides(base, rows, "instance")
        if actor.vampire_mode == VAMPIRE_MODE_ENABLE:
            base = {}
        elif actor.character_creature_id:
            base = VampireRules(actor.character_creature)._power_definition_rows()
        elif actor.creature_id:
            base = VampireRules(actor.creature)._power_definition_rows()
        else:
            base = {}
        rows = actor.vampire_power_overrides.select_related("power").prefetch_related(
            "power__semantic_effects"
        )
        return self._apply_power_overrides(base, rows, "gm")

    def effective_traits(self, *, include_weaknesses: bool = True) -> list[EffectiveVampireTrait]:
        if not self.is_vampire():
            return []
        resolved = self._trait_definition_rows()
        return sorted(
            resolved.values(),
            key=lambda entry: (entry.trait.sort_order, entry.trait.name.casefold(), entry.trait.id),
        )

    def effective_powers(self) -> list[EffectiveVampirePower]:
        if not self.is_vampire():
            return []
        return sorted(
            self._power_definition_rows().values(),
            key=lambda entry: (entry.power.sort_order, entry.power.name.casefold(), entry.power.id),
        )

    def power_ranks(self) -> int:
        """Each acquired power rank increases blood capacity by exactly one."""
        return sum(entry.rank for entry in self.effective_powers())

    def can_regenerate(self) -> bool:
        """Return whether semantic effects enable vampiric regeneration."""
        return self.semantic_flag(VAMPIRE_REGENERATION)

    def semantic_flag(self, target_key: str) -> bool:
        """Resolve one boolean flag directly from effective vampire semantic effects."""
        if not self.is_vampire():
            return False
        allowed_scopes = {
            "both",
            "character" if isinstance(self.actor, Character) else "creature",
        }
        effects = []
        for ownership in self.effective_traits(include_weaknesses=True):
            effects.extend(ownership.trait.semantic_effects.all())
        for ownership in self.effective_powers():
            effects.extend(
                effect
                for effect in ownership.power.semantic_effects.all()
                if effect.power_component != VampireTraitSemanticEffect.PowerComponent.WEAKNESS
                or ownership.weakness_is_active
            )
        enabled = False
        for effect in sorted(effects, key=lambda row: (int(row.priority), int(row.id or 0))):
            if (
                not effect.active_flag
                or effect.application_scope not in allowed_scopes
                or effect.target_domain != "rule_flag"
                or effect.target_key != target_key
            ):
                continue
            value = effect._coerce_scalar(effect.value)
            enabled = effect.operator != "unset_flag" and bool(value)
        return enabled

    def can_exceed_strength_race_maximum(self) -> bool:
        return self.semantic_flag(VAMPIRE_STRENGTH_OVER_RACE_MAXIMUM)

    def disallowed_school_ids(self) -> set[int]:
        """Return schools blocked by active vampire semantic effects."""
        if not self.is_vampire():
            return set()
        allowed_scopes = {
            "both",
            "character" if isinstance(self.actor, Character) else "creature",
        }
        blocked: set[int] = set()
        effect_groups = [
            (entry.trait.semantic_effects.all(), True)
            for entry in self.effective_traits(include_weaknesses=True)
        ]
        effect_groups.extend(
            (entry.power.semantic_effects.all(), entry.weakness_is_active)
            for entry in self.effective_powers()
        )
        for effects, weakness_is_active in effect_groups:
            for effect in effects:
                if (
                    effect.active_flag
                    and (
                        effect.power_component != VampireTraitSemanticEffect.PowerComponent.WEAKNESS
                        or weakness_is_active
                    )
                    and effect.application_scope in allowed_scopes
                    and effect.target_domain == "metadata"
                    and effect.target_key == "disallow_schools"
                ):
                    blocked.update(effect.target_schools.values_list("id", flat=True))
        return blocked

    def willpower(self) -> int:
        actor = self.actor
        if isinstance(actor, Character):
            return max(0, int(actor.get_engine(refresh=True).attributes().get(ATTR_WILL, 0)))
        from charsheet.engine.creature_engine import CreatureEngine

        source = actor
        if isinstance(actor, GameGroupCreature):
            source = actor.character_creature or actor.creature
            if source is None:
                return 0
        modifier = CreatureEngine(source).attribute_mod(ATTR_WILL)
        return max(0, int(modifier or 0) + 5)

    def school_ranks(self) -> int:
        if not isinstance(self.actor, Character):
            return 0
        return sum(
            int(entry.level or 0)
            for entry in self.actor.schools.select_related("school__type")
            if entry.school.type.slug in {SCHOOL_ARCANE, SCHOOL_COMBAT}
        )

    def capacity_bonus(self) -> int:
        actor = self.actor
        if isinstance(actor, Character):
            return int(actor.vampire_blood_capacity_bonus or 0)
        if isinstance(actor, Creature):
            return int(actor.vampire_blood_capacity_bonus_default or 0)
        if isinstance(actor, CharacterCreature):
            if actor.vampire_blood_capacity_bonus_override is not None:
                return int(actor.vampire_blood_capacity_bonus_override)
            return int(actor.creature.vampire_blood_capacity_bonus_default or 0) if actor.creature_id else 0
        return int(actor.vampire_blood_capacity_bonus or 0)

    def capacity_loss(self) -> int:
        actor = self.actor
        if isinstance(actor, Creature):
            return 0
        return max(0, int(actor.vampire_blood_capacity_loss or 0))

    def capacity_override(self) -> int | None:
        actor = self.actor
        if isinstance(actor, Character):
            return None
        return (
            None
            if getattr(actor, "vampire_blood_capacity_override", None) is None
            else max(0, int(actor.vampire_blood_capacity_override))
        )

    def blood_capacity(self) -> int:
        override = self.capacity_override()
        if override is not None:
            return max(0, override - self.capacity_loss())
        return max(
            0,
            self.willpower()
            + self.school_ranks()
            + self.power_ranks()
            + self.age_cycle()
            + self.capacity_bonus()
            - self.capacity_loss(),
        )

    def potential(self) -> int:
        return max(0, self.willpower() // 2)

    def resource_state(self) -> VampireResourceState:
        actor = self.actor
        if isinstance(actor, Creature):
            intelligent = int(actor.vampire_intelligent_blood_default or 0)
            animal = int(actor.vampire_animal_blood_default or 0)
        else:
            intelligent = int(actor.vampire_intelligent_blood or 0)
            animal = int(actor.vampire_animal_blood or 0)
        maximum = self.blood_capacity()
        intelligent = max(0, intelligent)
        animal = max(0, animal)
        overflow = max(0, intelligent + animal - maximum)
        if overflow:
            animal_reduction = min(animal, overflow)
            animal -= animal_reduction
            intelligent = max(0, intelligent - (overflow - animal_reduction))
        return VampireResourceState(intelligent, animal, maximum, self.potential())

    def warnings(self) -> list[str]:
        warnings: list[str] = []
        if not self.is_vampire():
            if not isinstance(self.actor, Character) and self._ownership_rows_for_warnings():
                warnings.append("Vampir-Traits sind hinterlegt, obwohl Vampirismus auf dieser Ebene deaktiviert ist.")
            return warnings
        if self.willpower() <= 0:
            warnings.append("Willenskraft fehlt; Blutvorrat und Potential benötigen einen manuellen SL-Wert.")
        state = self.resource_state()
        raw_total = int(getattr(self.actor, "vampire_intelligent_blood", 0) or 0) + int(
            getattr(self.actor, "vampire_animal_blood", 0) or 0
        )
        if raw_total > state.maximum:
            warnings.append("Der aktuelle Blutvorrat liegt über der Kapazität.")
        for row in self._ownership_rows_for_warnings():
            warnings.extend(row.validation_warnings())
        return warnings

    def _ownership_rows_for_warnings(self):
        actor = self.actor
        if isinstance(actor, Character):
            return []
        if isinstance(actor, Creature):
            return list(actor.vampire_power_defaults.select_related("power"))
        return list(actor.vampire_power_overrides.select_related("power"))

    def _require_runtime(self):
        if self.is_template:
            raise VampireRuleError("Laufzeitaktionen sind auf Kreaturenvorlagen nicht zulässig.")
        if not self.is_vampire():
            raise VampireRuleError("Diese Instanz ist kein Vampir.")
        if getattr(self.actor, "vampire_state", VAMPIRE_STATE_ACTIVE) == VAMPIRE_STATE_DESTROYED:
            raise VampireRuleError("Ein vernichteter Vampir kann keine Aktion ausführen.")

    def _save(self, *fields: str):
        if fields:
            self.actor.save(update_fields=list(dict.fromkeys(fields)))

    def _require_character_learning(self) -> Character:
        if not isinstance(self.actor, Character):
            raise VampireRuleError("Vampir-Traits werden für Kreaturen über ihre Override-Ebene verwaltet.")
        if not self.is_vampire():
            raise VampireRuleError("Zuerst muss der Erwerbsanker Vampirismus erlernt werden.")
        return self.actor

    @transaction.atomic
    def learn_power(
        self,
        power: VampirePower | int,
        *,
        without_weakness: bool = False,
    ) -> CharacterVampirePower:
        character = self._require_character_learning()
        definition = power if isinstance(power, VampirePower) else VampirePower.objects.get(pk=int(power))
        if not definition.is_active:
            raise VampireRuleError("Nur aktive Vampirkräfte können gelernt werden.")
        if not str(definition.weakness or "").strip():
            raise VampireRuleError("Der Vampirkraft ist noch keine feste Schwäche zugeordnet.")
        existing = CharacterVampirePower.objects.select_for_update().filter(
            character=character,
            power=definition,
        ).first()
        if existing is not None and not definition.can_be_learned_multiple_times:
            raise VampireRuleError("Diese Vampirkraft ist bereits erworben.")
        if existing is not None and without_weakness:
            raise VampireRuleError("Die Schwäche einer bereits erworbenen Kraft kann nur einmal freigekauft werden.")
        if existing is not None:
            cost = self.power_cost(without_weakness=False)
            if cost > int(character.current_experience or 0):
                raise VampireRuleError(f"Für diesen weiteren Rang werden {cost} EP benötigt.")
            existing.level = max(1, int(existing.level or 1)) + 1
            existing.full_clean()
            existing.save(update_fields=["level"])
            character.current_experience -= cost
            character.save(update_fields=["current_experience"])
            return existing
        ownership = CharacterVampirePower(
            character=character,
            power=definition,
            purchased_without_weakness=bool(without_weakness),
        )
        ownership.full_clean()
        cost = self.power_cost(without_weakness=ownership.purchased_without_weakness)
        if cost > int(character.current_experience or 0):
            raise VampireRuleError(f"Für diese Vampirkraft werden {cost} EP benötigt.")
        ownership.save()
        character.current_experience -= cost
        character.save(update_fields=["current_experience"])
        return ownership

    @transaction.atomic
    def learn_trait(self, trait: VampireTrait | int) -> CharacterVampireTrait:
        raise VampireRuleError(
            "Vampirische Vorzüge und Schwächen werden beim Vampirwerden automatisch zugeordnet."
        )

    @transaction.atomic
    def remove_trait_weakness(self, trait: VampireTrait | int) -> None:
        raise VampireRuleError(
            "Automatisch zugeordnete vampirische Schwächen können nicht im Lernmenü entfernt werden."
        )

    @transaction.atomic
    def buy_off_associated_weakness(self, power: VampirePower | int) -> CharacterVampirePower:
        character = self._require_character_learning()
        power_id = power.id if isinstance(power, VampirePower) else int(power)
        ownership = CharacterVampirePower.objects.select_for_update().select_related("power").filter(
            character=character,
            power_id=power_id,
        ).first()
        if ownership is None or not str(ownership.power.weakness or "").strip():
            raise VampireRuleError("Diese erworbene Kraft besitzt keine freikaufbare Schwäche.")
        if ownership.purchased_without_weakness:
            raise VampireRuleError("Diese Kraft wurde bereits ohne Schwäche erworben.")
        if ownership.weakness_bought_off:
            raise VampireRuleError("Die zugeordnete Schwäche wurde bereits freigekauft.")
        cost = VAMPIRE_WEAKNESS_REMOVAL_COST
        if cost > int(character.current_experience or 0):
            raise VampireRuleError(f"Für den Schwächenfreikauf werden {cost} EP benötigt.")
        ownership.weakness_bought_off = True
        ownership.full_clean()
        ownership.save(update_fields=["weakness_bought_off"])
        character.current_experience -= cost
        character.save(update_fields=["current_experience"])
        return ownership

    @transaction.atomic
    def purchase_age_cycle(self) -> int:
        character = self._require_character_learning()
        if AGE_CYCLE_COST > int(character.current_experience or 0):
            raise VampireRuleError(f"Ein weiterer Alterszyklus kostet {AGE_CYCLE_COST} EP.")
        character.vampire_age_cycle = max(1, int(character.vampire_age_cycle or 1)) + 1
        character.current_experience -= AGE_CYCLE_COST
        character.save(update_fields=["vampire_age_cycle", "current_experience"])
        return character.vampire_age_cycle

    @transaction.atomic
    def purchase_capacity(self, amount: int = 1) -> int:
        character = self._require_character_learning()
        amount = max(1, int(amount or 1))
        cost = self.capacity_bonus_cost(amount)
        if cost > int(character.current_experience or 0):
            raise VampireRuleError(f"Die zusätzliche Blutkapazität kostet {cost} EP.")
        character.vampire_blood_capacity_bonus += amount
        character.current_experience -= cost
        character.save(update_fields=["vampire_blood_capacity_bonus", "current_experience"])
        return character.vampire_blood_capacity_bonus

    @transaction.atomic
    def blood_sacrament(self, blood_amount: int, *, duration_rounds: int | None = None) -> dict[str, int]:
        self._require_runtime()
        if int(getattr(self.actor, "vampire_sacrament_rounds_remaining", 0) or 0) > 0:
            raise VampireRuleError("Ein bereits wirksames Blutsakrament ist nicht kumulativ.")
        amount = max(1, int(blood_amount or 1))
        self.activate_power("blutsakrament", blood_amount=amount)
        duration = SystemRandom().randint(1, 20) if duration_rounds is None else int(duration_rounds)
        if duration < 1 or duration > 20:
            raise VampireRuleError("Die bestätigte Wirkungsdauer des Blutsakraments muss zwischen 1 und 20 Runden liegen.")
        self.actor.vampire_sacrament_age_bonus = amount
        self.actor.vampire_sacrament_rounds_remaining = duration
        self._save("vampire_sacrament_age_bonus", "vampire_sacrament_rounds_remaining")
        return {"age_bonus": amount, "rounds_remaining": duration}

    @transaction.atomic
    def advance_round(self) -> int:
        """Advance only persisted vampire durations; no global combat clock is assumed."""
        self._require_runtime()
        remaining = int(getattr(self.actor, "vampire_sacrament_rounds_remaining", 0) or 0)
        if remaining <= 0:
            return 0
        remaining -= 1
        self.actor.vampire_sacrament_rounds_remaining = remaining
        if remaining == 0:
            self.actor.vampire_sacrament_age_bonus = 0
        self._save("vampire_sacrament_age_bonus", "vampire_sacrament_rounds_remaining")
        return remaining

    @transaction.atomic
    def gain_blood(self, amount: int, *, intelligent: bool) -> VampireResourceState:
        self._require_runtime()
        amount = max(0, int(amount or 0))
        state = self.resource_state()
        accepted = min(amount, max(0, state.maximum - state.total))
        field = "vampire_intelligent_blood" if intelligent else "vampire_animal_blood"
        setattr(self.actor, field, int(getattr(self.actor, field) or 0) + accepted)
        self._save(field)
        return self.resource_state()

    @transaction.atomic
    def adjust_animal_blood(self, delta: int) -> VampireResourceState:
        """Manually adjust animal/creature blood while preserving the shared capacity."""
        self._require_runtime()
        delta = int(delta or 0)
        if delta >= 0:
            return self.gain_blood(delta, intelligent=False)
        state = self.resource_state()
        self.actor.vampire_animal_blood = max(0, state.animal + delta)
        self._save("vampire_animal_blood")
        return self.resource_state()

    @transaction.atomic
    def adjust_animal_blood(self, delta: int) -> VampireResourceState:
        """Manually adjust animal/creature blood while preserving the shared capacity."""
        self._require_runtime()
        delta = int(delta or 0)
        if delta >= 0:
            return self.gain_blood(delta, intelligent=False)
        state = self.resource_state()
        self.actor.vampire_animal_blood = max(0, state.animal + delta)
        self._save("vampire_animal_blood")
        return self.resource_state()

    @transaction.atomic
    def spend_intelligent_blood(self, amount: int, *, enforce_potential: bool = True) -> VampireResourceState:
        self._require_runtime()
        amount = max(0, int(amount or 0))
        state = self.resource_state()
        if enforce_potential and amount > state.potential:
            raise VampireRuleError("Die Blutkosten überschreiten das Potential dieser Handlung.")
        if amount > state.intelligent:
            raise VampireRuleError("Nicht genug Blut intelligenter Wesen.")
        self.actor.vampire_intelligent_blood = state.intelligent - amount
        self._save("vampire_intelligent_blood")
        return self.resource_state()

    @transaction.atomic
    def sunrise(self, *, animal_blood: int, intelligent_blood: int) -> dict[str, Any]:
        self._require_runtime()
        animal_blood = max(0, int(animal_blood or 0))
        intelligent_blood = max(0, int(intelligent_blood or 0))
        state = self.resource_state()
        if self.actor.vampire_state == VAMPIRE_STATE_TORPOR:
            if animal_blood or intelligent_blood:
                raise VampireRuleError("In Starre entsteht bei Sonnenaufgang kein täglicher Blutverbrauch.")
            self.actor.vampire_day_count = int(self.actor.vampire_day_count or 0) + 1
            self._save("vampire_day_count")
            return {
                "resource": self.resource_state(),
                "shortfall": 0,
                "pending_starvation": int(self.actor.vampire_pending_starvation or 0),
            }
        required = min(DAILY_BLOOD_COST, state.total)
        if animal_blood + intelligent_blood != required:
            raise VampireRuleError("Die Blutverteilung muss den verfügbaren Tagesverbrauch exakt abdecken.")
        if animal_blood > state.animal or intelligent_blood > state.intelligent:
            raise VampireRuleError("Die gewählte Blutart ist nicht in ausreichender Menge vorhanden.")
        self.actor.vampire_animal_blood = state.animal - animal_blood
        self.actor.vampire_intelligent_blood = state.intelligent - intelligent_blood
        self.actor.vampire_day_count = int(self.actor.vampire_day_count or 0) + 1
        shortfall = DAILY_BLOOD_COST - required
        if shortfall:
            self.actor.vampire_pending_starvation = int(self.actor.vampire_pending_starvation or 0) + 1
        self._save(
            "vampire_animal_blood",
            "vampire_intelligent_blood",
            "vampire_day_count",
            "vampire_pending_starvation",
        )
        return {
            "resource": self.resource_state(),
            "shortfall": shortfall,
            "pending_starvation": int(self.actor.vampire_pending_starvation or 0),
        }

    @transaction.atomic
    def record_qualifying_kill(self) -> int:
        self._require_runtime()
        self.actor.vampire_last_qualifying_kill_day = int(self.actor.vampire_day_count or 0)
        self._save("vampire_last_qualifying_kill_day")
        return self.actor.vampire_last_qualifying_kill_day

    def has_recent_qualifying_kill(self) -> bool:
        last = getattr(self.actor, "vampire_last_qualifying_kill_day", None)
        if last is None:
            return False
        return 0 <= int(getattr(self.actor, "vampire_day_count", 0) or 0) - int(last) <= POWER_KILL_WINDOW_DAYS

    @transaction.atomic
    def activate_power(self, power: VampirePower | int | str, *, blood_amount: int | None = None) -> dict[str, Any]:
        self._require_runtime()
        if isinstance(power, VampirePower):
            definition = power
        elif isinstance(power, int):
            definition = VampirePower.objects.get(pk=power)
        else:
            definition = VampirePower.objects.get(slug=str(power))
        owned = next(
            (
                entry
                for entry in self.effective_powers()
                if entry.power.id == definition.id
            ),
            None,
        )
        if owned is None:
            raise VampireRuleError("Die Vampirkraft ist nicht wirksam im Besitz dieser Instanz.")
        if not self.has_recent_qualifying_kill():
            raise VampireRuleError("Für Vampirkräfte fehlt eine qualifizierende Tötung innerhalb der letzten 28 Tage.")
        cost = int(definition.blood_cost if definition.blood_cost is not None else blood_amount or 0)
        self.spend_intelligent_blood(cost, enforce_potential=True)
        return {
            "power": definition,
            "spent_blood": cost,
            "resource": self.resource_state(),
        }

    @transaction.atomic
    def invest_regeneration(
        self,
        blood_amount: int | None,
        *,
        hard_to_heal: bool,
        wound_grade: int,
        damage_type: str = "T",
        aggravated: bool = False,
    ) -> dict[str, Any]:
        self._require_runtime()
        if not self.can_regenerate():
            raise VampireRuleError("Vampirische Regeneration wurde nicht als Fähigkeit erworben.")
        wound_grades = max(1, int(wound_grade or 1))
        cost_per_wound_grade = HARD_REGENERATION_COST if hard_to_heal else REGENERATION_COST
        required = cost_per_wound_grade * wound_grades
        # Partial regeneration was removed from the UI and rules workflow. Discard
        # stale investments created by the former implementation before validating
        # this all-or-nothing action.
        self.actor.vampire_regeneration_blood = 0
        self.actor.vampire_regeneration_target_cost = 0
        remaining = required
        state = self.resource_state()
        if state.intelligent < remaining:
            raise VampireRuleError(
                f"Für {wound_grades} Wundgrad{'e' if wound_grades != 1 else ''} werden {remaining} BP benötigt; verfügbar sind {state.intelligent}."
            )
        if state.potential < remaining:
            raise VampireRuleError(
                f"Die Regeneration benötigt {remaining} BP in einer Handlung; das Potential beträgt {state.potential}."
            )
        investment = remaining
        self.spend_intelligent_blood(investment, enforce_potential=True)
        healed = self._heal_damage(
            self.wound_grade_life_points() * wound_grades,
            damage_type=damage_type,
            aggravated=aggravated,
        )
        if healed <= 0:
            raise VampireRuleError("Für die gewählte Regeneration ist kein passender Schaden vorhanden.")
        self._refresh_life_state()
        save_fields = [
            "vampire_regeneration_blood",
            "vampire_regeneration_target_cost",
            "current_aggravated_damage",
            "vampire_state",
        ]
        if isinstance(self.actor, CharacterCreature):
            save_fields.append("current_damage")
        else:
            save_fields.extend(("current_stun_damage", "current_lethal_damage"))
        self._save(*save_fields)
        return {
            "required": required,
            "wound_grades": wound_grades,
            "cost_per_wound_grade": cost_per_wound_grade,
            "invested": int(self.actor.vampire_regeneration_blood or 0),
            "healed": healed,
            "resource": self.resource_state(),
            "state": self.actor.vampire_state,
        }

    def wound_grade_life_points(self) -> int:
        """Return the actor-local LP width of one wound grade."""
        actor = self.actor
        if isinstance(actor, Character):
            thresholds = sorted(actor.get_engine(refresh=True).wound_thresholds())
            return max(1, int(thresholds[0])) if thresholds else 1
        source = actor.character_creature or actor.creature if isinstance(actor, GameGroupCreature) else actor
        if source is not None:
            from charsheet.engine.creature_engine import CreatureEngine

            rows = CreatureEngine(source).wound_rows()
            if rows:
                return max(1, int(rows[0]["threshold"]))
        return 1

    def _heal_damage(self, amount: int, *, damage_type: str, aggravated: bool) -> int:
        actor = self.actor
        before = int(actor.current_damage)
        if damage_type == "total":
            amount = max(0, int(amount or 0))
            if isinstance(actor, CharacterCreature):
                aggravated_damage = int(actor.current_aggravated_damage or 0)
                healed = min(amount, aggravated_damage if aggravated else max(0, int(actor.current_damage or 0) - aggravated_damage))
                actor.current_damage = max(0, int(actor.current_damage or 0) - healed)
                if aggravated:
                    actor.current_aggravated_damage = max(0, aggravated_damage - healed)
                return healed
            if aggravated:
                healed = min(amount, int(actor.current_aggravated_damage or 0))
                actor.current_aggravated_damage = max(0, int(actor.current_aggravated_damage or 0) - healed)
                actor.current_lethal_damage = max(0, int(actor.current_lethal_damage or 0) - healed)
                return healed
            stun_healed = min(amount, int(actor.current_stun_damage or 0))
            actor.current_stun_damage = max(0, int(actor.current_stun_damage or 0) - stun_healed)
            remaining = amount - stun_healed
            normal_lethal = max(0, int(actor.current_lethal_damage or 0) - int(actor.current_aggravated_damage or 0))
            lethal_healed = min(remaining, normal_lethal)
            actor.current_lethal_damage = max(0, int(actor.current_lethal_damage or 0) - lethal_healed)
            return stun_healed + lethal_healed
        if isinstance(actor, Character):
            actor.adjust_damage(
                damage_type=damage_type,
                action="heal",
                amount=amount,
                stun_max=self.max_life_points(),
                aggravated=aggravated,
            )
        elif isinstance(actor, GameGroupCreature):
            actor.adjust_damage(
                damage_type=damage_type,
                action="heal",
                amount=amount,
                stun_max=self.max_life_points(),
                aggravated=aggravated,
            )
        else:
            if aggravated:
                healed = min(amount, int(actor.current_aggravated_damage or 0))
                actor.current_aggravated_damage -= healed
            else:
                healed = min(
                    amount,
                    max(0, int(actor.current_damage or 0) - int(actor.current_aggravated_damage or 0)),
                )
            actor.current_damage = max(0, int(actor.current_damage or 0) - healed)
        return max(0, before - int(actor.current_damage))

    def max_life_points(self) -> int:
        actor = self.actor
        if isinstance(actor, Character):
            thresholds = actor.get_engine(refresh=True).wound_thresholds()
        else:
            from charsheet.engine.creature_engine import CreatureEngine

            source = actor
            if isinstance(actor, GameGroupCreature):
                source = actor.character_creature or actor.creature
            thresholds = (
                [row["threshold"] for row in CreatureEngine(source).wound_rows()]
                if source is not None
                else []
            )
        return max((int(value) for value in thresholds), default=0)

    def destruction_load(self) -> int:
        total = int(self.actor.current_damage)
        aggravated = min(total, int(self.actor.current_aggravated_damage or 0))
        return max(0, total - aggravated) + aggravated * 4

    def _refresh_life_state(self):
        maximum = self.max_life_points()
        if maximum <= 0:
            return
        if self.destruction_load() > maximum * 4:
            self.actor.vampire_state = VAMPIRE_STATE_DESTROYED
        elif int(self.actor.current_damage) >= maximum:
            self.actor.vampire_state = VAMPIRE_STATE_TORPOR
        elif self.actor.vampire_state == VAMPIRE_STATE_TORPOR:
            self.actor.vampire_state = VAMPIRE_STATE_ACTIVE

    @transaction.atomic
    def evaluate_life_state(self) -> str:
        """Re-evaluate Starre and destruction after an external damage edit."""
        if self.is_template:
            raise VampireRuleError("Laufzeitaktionen sind auf Kreaturenvorlagen nicht zulässig.")
        if not self.is_vampire():
            raise VampireRuleError("Diese Instanz ist kein Vampir.")
        self._refresh_life_state()
        self._save("vampire_state")
        return self.actor.vampire_state

    @transaction.atomic
    def apply_damage(self, amount: int, *, aggravated: bool, damage_type: str = "T") -> dict[str, Any]:
        self._require_runtime()
        amount = max(0, int(amount or 0))
        actor = self.actor
        if isinstance(actor, Character):
            actor.adjust_damage(
                damage_type=damage_type,
                action="damage",
                amount=amount,
                stun_max=self.max_life_points(),
                aggravated=aggravated,
            )
        elif isinstance(actor, GameGroupCreature):
            actor.adjust_damage(
                damage_type=damage_type,
                action="damage",
                amount=amount,
                stun_max=self.max_life_points(),
                aggravated=aggravated,
            )
        else:
            actor.current_damage = int(actor.current_damage or 0) + amount
            if aggravated:
                actor.current_aggravated_damage = int(actor.current_aggravated_damage or 0) + amount
        self._refresh_life_state()
        fields = ["current_aggravated_damage", "vampire_state"]
        fields.append("current_damage" if isinstance(actor, CharacterCreature) else "current_lethal_damage")
        if not isinstance(actor, CharacterCreature) and damage_type == "B":
            fields.append("current_stun_damage")
        self._save(*fields)
        return {
            "damage": int(actor.current_damage),
            "aggravated_damage": int(actor.current_aggravated_damage or 0),
            "destruction_load": self.destruction_load(),
            "state": actor.vampire_state,
        }

    @transaction.atomic
    def resolve_starvation(self, *, damage_type: str, wound_grade: int) -> dict[str, Any]:
        self._require_runtime()
        if int(self.actor.vampire_pending_starvation or 0) <= 0:
            raise VampireRuleError("Es ist keine Blutmangelkonsequenz offen.")
        if damage_type not in {"B", "T"}:
            raise VampireRuleError("Die Schadensart muss ausdrücklich als B oder T gewählt werden.")
        self.actor.vampire_pending_starvation -= 1
        self._save("vampire_pending_starvation")
        result = self.apply_damage(max(1, int(wound_grade or 1)), aggravated=False, damage_type=damage_type)
        result["pending_starvation"] = int(self.actor.vampire_pending_starvation or 0)
        return result

    @transaction.atomic
    def behead(self, *, confirmed: bool) -> str:
        self._require_runtime()
        if not confirmed:
            raise VampireRuleError("Die erfolgreiche Enthauptung muss bestätigt werden.")
        self.actor.vampire_state = VAMPIRE_STATE_DESTROYED
        self._save("vampire_state")
        return self.actor.vampire_state

    @transaction.atomic
    def stake(self, *, net_damage: int, constitution: int) -> str:
        self._require_runtime()
        if int(net_damage or 0) < max(0, int(constitution or 0)) * 2:
            raise VampireRuleError("Der bestätigte Nettoschaden erreicht nicht das Doppelte der Konstitution.")
        self.actor.vampire_state = VAMPIRE_STATE_DESTROYED
        self._save("vampire_state")
        return self.actor.vampire_state

    @transaction.atomic
    def blood_baptism(self, *, success: bool, extra_blood: int = 0) -> dict[str, Any]:
        self._require_runtime()
        extra_blood = max(0, int(extra_blood or 0))
        total_given = 1 + extra_blood
        if int(self.actor.vampire_intelligent_blood or 0) < total_given:
            raise VampireRuleError("Für die Bluttaufe und die bestätigten zusätzlichen Blutpunkte fehlt intelligentes Blut.")
        self.actor.vampire_intelligent_blood -= total_given
        self.actor.vampire_blood_capacity_loss = int(self.actor.vampire_blood_capacity_loss or 0) + 1
        self._save("vampire_intelligent_blood", "vampire_blood_capacity_loss")
        return {
            "success": bool(success),
            "permanent_capacity_loss": 1,
            "confirmed_extra_blood_for_target": extra_blood,
            "resource": self.resource_state(),
        }

    @transaction.atomic
    def blood_ritual(self, candidate_power_ids: Iterable[int], *, victim_destroyed: bool) -> VampirePower:
        self._require_runtime()
        if not victim_destroyed:
            raise VampireRuleError("Die Vernichtung des ausgesaugten Vampirs muss bestätigt werden.")
        owned_ids = {entry.power.id for entry in self.effective_powers()}
        candidates = list(
            VampirePower.objects.filter(
                pk__in=[int(value) for value in candidate_power_ids],
                is_active=True,
            ).exclude(pk__in=owned_ids)
        )
        if not candidates:
            raise VampireRuleError("Das Opfer besitzt keine noch unbekannte bestätigte Vampirkraft.")
        selected = SystemRandom().choice(candidates)
        if isinstance(self.actor, Character):
            CharacterVampirePower.objects.create(character=self.actor, power=selected)
        else:
            override_model = self.actor.vampire_power_overrides.model
            override_model.objects.update_or_create(
                creature=self.actor,
                power=selected,
                defaults={
                    "mode": VampireTraitOverrideMode.ADD,
                    "purchased_without_weakness": False,
                    "weakness_bought_off": False,
                },
            )
        return selected


def character_uses_blood(character: Character) -> bool:
    """Small integration seam used by existing KP consumers."""
    return VampireRules(character).is_vampire()
