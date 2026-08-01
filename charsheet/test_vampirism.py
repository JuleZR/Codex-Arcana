from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from charsheet.constants import ATTR_ST, ATTR_WILL, QUALITY_COMMON, VAMPIRE_MODE_ENABLE, VAMPIRE_STATE_TORPOR
from charsheet.engine.magic_engine import MagicEngine
from charsheet.engine.character_creation_engine import CharacterCreationEngine
from charsheet.engine.vampire_engine import VampireRuleError, VampireRules
from charsheet.learning_rules import calc_attribute_total_cost
from charsheet.learning import process_learning_submission
from charsheet.models import (
    Attribute,
    Character,
    CharacterAttribute,
    CharacterCreature,
    CharacterCreationDraft,
    CharacterCreatureVampireTrait,
    CharacterTrait,
    CharacterVampireTrait,
    Creature,
    CreatureVampireTrait,
    GameGroup,
    GameGroupCreature,
    GameGroupCreatureVampireTrait,
    Quality,
    Race,
    RaceAttributeLimit,
    Trait,
    VampireTrait,
    VampireTraitOverrideMode,
    VampireTraitSemanticEffect,
)


class VampireRulesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="vampire-test", password="test12345")
        self.race = Race.objects.create(name="Vampir-Testvolk")
        self.will = Attribute.objects.create(name="Vampir-Test-Willenskraft", short_name=ATTR_WILL)
        self.strength = Attribute.objects.create(name="Vampir-Test-Stärke", short_name=ATTR_ST)
        RaceAttributeLimit.objects.create(race=self.race, attribute=self.will, min_value=1, max_value=18)
        RaceAttributeLimit.objects.create(race=self.race, attribute=self.strength, min_value=1, max_value=18)
        self.character = Character.objects.create(
            owner=self.user,
            name="Dracula Test",
            race=self.race,
            current_experience=100,
        )
        CharacterAttribute.objects.create(character=self.character, attribute=self.will, base_value=10)
        CharacterAttribute.objects.create(character=self.character, attribute=self.strength, base_value=18)
        self.anchor = Trait.objects.get(slug="adv_vampire")
        CharacterTrait.objects.create(owner=self.character, trait=self.anchor, trait_level=1)
        self.aura = VampireTrait.objects.get(slug="aura-sehen")
        self.blood_sacrament = VampireTrait.objects.get(slug="blutsakrament")

    def test_rulebook_seed_uses_one_typed_trait_model(self):
        self.assertEqual(VampireTrait.objects.filter(trait_type="base").count(), 0)
        self.assertEqual(VampireTrait.objects.filter(trait_type="power").count(), 26)
        self.assertEqual(VampireTrait.objects.filter(trait_type="weakness").count(), 25)
        self.assertFalse(hasattr(self.character, "vampirepower_set"))
        self.assertTrue(Trait.objects.filter(slug="adv_vampire", name="Vampir").exists())
        self.assertFalse(Trait.objects.filter(slug="vampirismus").exists())
        self.assertFalse(VampireTrait.objects.filter(slug="grundvampirismus").exists())
        self.assertFalse(VampireTraitSemanticEffect.objects.filter(target_key__startswith="vampire_weakness_").exists())

    def test_admin_semantic_effect_form_maps_simple_dropdowns_without_losing_scaling(self):
        from charsheet.admin import VampireTraitSemanticEffectAdminForm

        form = VampireTraitSemanticEffectAdminForm(
            data={
                "trait": self.aura.pk,
                "application_scope": VampireTraitSemanticEffect.ApplicationScope.BOTH,
                "sort_order": 0,
                "active_flag": True,
                "effect_area": "attribute",
                "simple_target": f"attribute:{ATTR_ST}",
                "simple_operator": "flat_add",
                "simple_value": "2",
                "vampire_scaling": "vampire_age_cycle",
                "condition_text": "",
            }
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())
        effect = form.save()
        self.assertEqual(effect.target_domain, "attribute")
        self.assertEqual(effect.target_key, ATTR_ST)
        self.assertEqual(effect.operator, "flat_add")
        self.assertEqual(effect.value, "2")
        self.assertEqual(effect.mode, "scaled")
        self.assertEqual(effect.scaling["scale_source"], "vampire_age_cycle")

    def test_admin_form_can_round_trip_every_seeded_vampire_effect_target(self):
        from charsheet.admin import VampireTraitSemanticEffectAdminForm

        expected_areas = {"derived_stat"}
        seen_areas = set()
        for effect in VampireTraitSemanticEffect.objects.select_related("trait"):
            form = VampireTraitSemanticEffectAdminForm(instance=effect)
            area = form.initial.get("effect_area")
            target = form.initial.get("simple_target")
            target_values = {value for value, _label in form.fields["simple_target"].choices}
            self.assertEqual(area, effect.target_domain if effect.target_domain != "derived_stat" else "defense")
            self.assertEqual(target, f"{area}:{effect.target_key}" if area != "defense" else f"defense:{effect.target_key}")
            self.assertIn(target, target_values, f"Missing admin target for {effect}")
            seen_areas.add(effect.target_domain)
        self.assertTrue(expected_areas.issubset(seen_areas))

    def test_admin_form_uses_domain_specific_boolean_operators(self):
        from charsheet.admin import VampireTraitSemanticEffectAdminForm

        form = VampireTraitSemanticEffectAdminForm(
            data={
                "trait": self.aura.pk,
                "application_scope": VampireTraitSemanticEffect.ApplicationScope.BOTH,
                "sort_order": 0,
                "active_flag": True,
                "effect_area": "rule_flag",
                "simple_target": "rule_flag:wound_penalty_ignore",
                "simple_operator": "set_flag",
                "vampire_scaling": "",
                "condition_text": "",
            }
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())
        effect = form.save()
        self.assertEqual(effect.operator, "set_flag")
        self.assertEqual(effect.value, "true")

    def test_anchor_derives_status_without_a_synthetic_base_trait(self):
        rules = VampireRules(self.character)
        effective = {entry.trait.slug for entry in rules.effective_traits()}
        self.assertTrue(rules.is_vampire())
        self.assertNotIn("grundvampirismus", effective)
        self.assertFalse(self.anchor.semantic_effects.exists())
        flags = self.character.get_engine(refresh=True).resolve_flags()
        self.assertTrue(flags["wound_penalty_ignore"])
        self.assertTrue(flags["can_act_while_out_of_action"])

    def test_in_play_anchor_requires_confirmed_baptism_at_exact_zero_lp_boundary(self):
        CharacterTrait.objects.filter(owner=self.character, trait=self.anchor).delete()
        self.character.__dict__.pop("_is_vampire_cache", None)
        constitution = Attribute.objects.create(name="Vampir-Test-Konstitution", short_name="KON")
        RaceAttributeLimit.objects.create(race=self.race, attribute=constitution, min_value=1, max_value=18)
        CharacterAttribute.objects.create(character=self.character, attribute=constitution, base_value=5)

        self.character.current_lethal_damage = 29
        self.character.vampire_baptism_confirmed = True
        self.character.save(update_fields=["current_lethal_damage", "vampire_baptism_confirmed"])
        self.assertFalse(self.character.is_at_vampire_baptism_threshold)

        self.character.current_lethal_damage = 30
        self.character.vampire_baptism_confirmed = False
        self.character.save(update_fields=["current_lethal_damage", "vampire_baptism_confirmed"])
        self.assertTrue(self.character.is_at_vampire_baptism_threshold)
        level, message = process_learning_submission(
            self.character,
            {"learn_trait_add_adv_vampire": "1"},
        )
        self.assertEqual(level, "error")
        self.assertIn("bestätigten Bluttaufe", message)

        self.character.vampire_baptism_confirmed = True
        self.character.save(update_fields=["vampire_baptism_confirmed"])
        level, _message = process_learning_submission(
            self.character,
            {"learn_trait_add_adv_vampire": "1"},
        )
        self.assertEqual(level, "success")
        self.assertTrue(CharacterTrait.objects.filter(owner=self.character, trait=self.anchor).exists())
        self.character.refresh_from_db()
        self.assertFalse(self.character.vampire_baptism_confirmed)

        CharacterTrait.objects.filter(owner=self.character, trait=self.anchor).delete()
        self.character.__dict__.pop("_is_vampire_cache", None)
        self.character.current_lethal_damage = 31
        self.character.save(update_fields=["current_lethal_damage"])
        self.assertFalse(self.character.is_at_vampire_baptism_threshold)

    def test_character_sheet_renders_shared_vampire_blood_resource(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("character_sheet", args=[self.character.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gesamter Blutvorrat")
        self.assertContains(response, "Blut intelligenter Wesen verringern")
        self.assertContains(response, "Tier-/Kreaturenblut verringern")
        self.assertContains(response, 'id="learn-tab-vampire"')
        self.assertContains(response, 'id="learn-panel-vampire"')

    def test_non_vampire_learning_menu_has_no_vampire_tab(self):
        mortal = Character.objects.create(owner=self.user, name="Mortal Test", race=self.race)
        self.client.force_login(self.user)
        response = self.client.get(reverse("character_sheet", args=[mortal.id]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="learn-tab-vampire"')

    def test_vampire_values_use_regular_learning_submission(self):
        start_age = self.character.vampire_age_cycle
        start_capacity = self.character.vampire_blood_capacity_bonus
        level, _message = process_learning_submission(
            self.character,
            {"learn_vampire_age_add": "1", "learn_vampire_capacity_add": "1"},
        )
        self.assertEqual(level, "success")
        self.character.refresh_from_db()
        self.assertEqual(self.character.vampire_age_cycle, start_age + 1)
        self.assertEqual(self.character.vampire_blood_capacity_bonus, start_capacity + 1)

    def test_manual_animal_blood_adjustment_uses_shared_capacity(self):
        rules = VampireRules(self.character)
        maximum = rules.resource_state().maximum
        self.character.vampire_intelligent_blood = maximum - 1
        self.character.vampire_animal_blood = 0
        self.character.save(update_fields=["vampire_intelligent_blood", "vampire_animal_blood"])

        state = rules.adjust_animal_blood(5)
        self.assertEqual(state.animal, 1)
        self.assertEqual(state.total, maximum)

        state = rules.adjust_animal_blood(-5)
        self.assertEqual(state.animal, 0)

    def test_animal_blood_action_supports_live_meter_updates(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("vampire_character_action", args=[self.character.id, "adjust-animal-blood"]),
            {"delta": 1, "ajax": 1},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["animal_blood"], 1)

    def test_power_automatically_applies_associated_weakness_until_buyoff(self):
        ownership = CharacterVampireTrait.objects.create(
            character=self.character,
            trait=self.aura,
            rank=1,
        )
        rules = VampireRules(self.character)
        self.assertIn("tiererkennung", {entry.trait.slug for entry in rules.effective_traits()})
        ownership.associated_weakness_bought_off = True
        ownership.save(update_fields=["associated_weakness_bought_off"])
        self.assertNotIn("tiererkennung", {entry.trait.slug for entry in rules.effective_traits()})

    def test_character_ownership_is_strict_but_creature_rows_warn(self):
        invalid = CharacterVampireTrait(character=self.character, trait=self.aura, rank=2)
        with self.assertRaises(ValidationError):
            invalid.full_clean()
        creature = self._creature()
        row = CreatureVampireTrait.objects.create(creature=creature, trait=self.aura, rank=2)
        self.assertTrue(row.validation_warnings())

    def test_regeneration_is_not_partially_paid_when_potential_is_too_low(self):
        self.character.vampire_intelligent_blood = 10
        self.character.current_lethal_damage = 5
        self.character.save(update_fields=["vampire_intelligent_blood", "current_lethal_damage"])
        with self.assertRaises(VampireRuleError):
            VampireRules(self.character).invest_regeneration(
                None, hard_to_heal=True, wound_grade=1, damage_type="total"
            )
        self.character.refresh_from_db()
        self.assertEqual(self.character.vampire_intelligent_blood, 10)
        self.assertEqual(self.character.current_lethal_damage, 5)
        self.assertEqual(self.character.vampire_regeneration_blood, 0)

    def test_regeneration_cost_depends_on_wound_grades_and_heals_damage(self):
        self.character.vampire_intelligent_blood = 10
        self.character.current_lethal_damage = 10
        self.character.save(update_fields=["vampire_intelligent_blood", "current_lethal_damage"])
        result = VampireRules(self.character).invest_regeneration(
            None, hard_to_heal=False, wound_grade=2, damage_type="T"
        )
        self.assertEqual(result["required"], 4)
        self.assertEqual(result["healed"], 2)
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_lethal_damage, 8)
        self.assertEqual(self.character.vampire_intelligent_blood, 6)

    def test_regeneration_does_not_start_without_full_blood_cost_available(self):
        self.character.vampire_intelligent_blood = 1
        self.character.current_lethal_damage = 5
        self.character.save(update_fields=["vampire_intelligent_blood", "current_lethal_damage"])
        with self.assertRaises(VampireRuleError):
            VampireRules(self.character).invest_regeneration(
                None, hard_to_heal=False, wound_grade=1, damage_type="T"
            )
        self.character.refresh_from_db()
        self.assertEqual(self.character.vampire_intelligent_blood, 1)
        self.assertEqual(self.character.current_lethal_damage, 5)
        self.assertEqual(self.character.vampire_regeneration_blood, 0)

    def test_regeneration_discards_obsolete_partial_payment_and_heals(self):
        self.character.vampire_intelligent_blood = 10
        self.character.current_lethal_damage = 5
        self.character.vampire_regeneration_blood = 1
        self.character.vampire_regeneration_target_cost = 8
        self.character.save()
        result = VampireRules(self.character).invest_regeneration(
            None, hard_to_heal=False, wound_grade=1, damage_type="total"
        )
        self.assertGreater(result["healed"], 0)
        self.character.refresh_from_db()
        self.assertEqual(self.character.vampire_regeneration_blood, 0)
        self.assertEqual(self.character.vampire_regeneration_target_cost, 0)
        self.assertEqual(self.character.vampire_intelligent_blood, 8)

    def test_regeneration_action_returns_live_damage_and_blood_state(self):
        self.character.vampire_intelligent_blood = 10
        self.character.current_stun_damage = 3
        self.character.current_lethal_damage = 4
        self.character.save()
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("vampire_character_action", args=[self.character.id, "regenerate"]),
            {"wound_grade": 1, "hard_to_heal": "0", "ajax": 1},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["healed"], 1)
        self.assertEqual(payload["current_stun_damage"], 2)
        self.assertEqual(payload["current_lethal_damage"], 4)
        self.assertEqual(payload["intelligent_blood"], 8)

    def test_blood_types_capacity_daily_use_and_torpor_exemption(self):
        self.character.vampire_age_cycle = 2
        self.character.vampire_blood_capacity_bonus = 3
        self.character.vampire_intelligent_blood = 4
        self.character.vampire_animal_blood = 2
        self.character.save()
        rules = VampireRules(self.character)
        self.assertEqual(rules.blood_capacity(), 15)
        result = rules.sunrise(animal_blood=2, intelligent_blood=0)
        self.assertEqual(result["shortfall"], 0)
        self.character.refresh_from_db()
        self.assertEqual(self.character.vampire_intelligent_blood, 4)
        self.character.vampire_state = VAMPIRE_STATE_TORPOR
        self.character.save(update_fields=["vampire_state"])
        day = self.character.vampire_day_count
        rules.sunrise(animal_blood=0, intelligent_blood=0)
        self.character.refresh_from_db()
        self.assertEqual(self.character.vampire_day_count, day + 1)
        self.assertEqual(self.character.vampire_intelligent_blood, 4)

    def test_magic_resource_normalization_uses_intelligent_blood_without_touching_kp(self):
        self.character.vampire_intelligent_blood = 5
        self.character.vampire_animal_blood = 3
        self.character.current_arcane_power = 99
        self.character.save()
        resource = MagicEngine(self.character).normalize_current_arcane_power()
        self.assertEqual(resource["resource_type"], "blood")
        self.assertEqual(resource["current_arcane_power"], 5)
        self.assertEqual(self.character.current_arcane_power, 99)

    def test_aggravated_damage_is_a_subset_not_a_second_track(self):
        self.character.current_lethal_damage = 5
        self.character.current_aggravated_damage = 2
        self.character.save()
        rules = VampireRules(self.character)
        self.assertEqual(rules.destruction_load(), 11)
        self.character.adjust_damage(
            damage_type="T",
            action="heal",
            amount=1,
            stun_max=20,
            aggravated=False,
        )
        self.assertEqual(self.character.current_lethal_damage, 4)
        self.assertEqual(self.character.current_aggravated_damage, 2)

    def test_template_instance_and_gm_trait_overrides(self):
        creature = self._creature(
            vampire_default_enabled=True,
            vampire_intelligent_blood_default=3,
            vampire_animal_blood_default=2,
        )
        CreatureVampireTrait.objects.create(creature=creature, trait=self.aura, rank=1)
        companion = CharacterCreature.objects.create(owner=self.character, creature=creature)
        self.assertEqual(companion.vampire_intelligent_blood, 3)
        self.assertEqual(companion.vampire_animal_blood, 2)
        CharacterCreatureVampireTrait.objects.create(
            creature=companion,
            trait=self.aura,
            mode=VampireTraitOverrideMode.REMOVE,
        )
        self.assertNotIn("aura-sehen", {entry.trait.slug for entry in VampireRules(companion).effective_traits()})
        group = GameGroup.objects.create(name="Vampir-Testgruppe", creator=self.user)
        card = GameGroupCreature.objects.create(
            group=group,
            character_creature=companion,
            vampire_mode=VAMPIRE_MODE_ENABLE,
        )
        GameGroupCreatureVampireTrait.objects.create(
            creature=card,
            trait=self.aura,
            mode=VampireTraitOverrideMode.ADD,
            rank=1,
        )
        self.assertIn("aura-sehen", {entry.trait.slug for entry in VampireRules(card).effective_traits()})

    def test_learning_never_refunds_and_uses_central_values(self):
        rules = VampireRules(self.character)
        ownership = rules.learn_power(self.aura)
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_experience, 85)
        rules.buy_off_associated_weakness(ownership.trait_id)
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_experience, 80)
        rules.purchase_age_cycle()
        rules.purchase_capacity(2)
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_experience, 64)
        with self.assertRaises(VampireRuleError):
            rules.learn_power(self.aura)

    def test_creation_draft_uses_the_same_trait_age_and_capacity_values(self):
        draft = CharacterCreationDraft.objects.create(
            owner=self.user,
            race=self.race,
            current_phase=4,
            state={
                "phase_4": {
                    "advantages": {"adv_vampire": 1},
                    "vampire": {
                        "age_cycle": 2,
                        "capacity_bonus": 2,
                        "traits": {"aura-sehen": {"rank": 1, "bought_off": False}},
                    },
                }
            },
        )
        engine = CharacterCreationEngine(draft)
        self.assertEqual(engine.vampire_creation_cost(), 31)
        self.assertEqual(engine.sum_phase_4_advantages_cost(), 46)
        self.assertEqual(engine.sum_phase_4_rest_cost(), 0)
        self.assertTrue(engine.vampire_configuration_is_valid())

        draft.state = {
            "phase_4": {
                "advantages": {"adv_vampire": 1},
                "vampire": {"age_cycle": 6},
            }
        }
        draft.save(update_fields=["state"])
        age_six_engine = CharacterCreationEngine(draft)
        self.assertEqual(age_six_engine.vampire_creation_cost(), 50)
        self.assertEqual(age_six_engine.sum_phase_4_advantages_cost(), 65)
        self.client.force_login(self.user)
        response = self.client.get(reverse("create_character"), {"draft": draft.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="phase4VampireSystem"')
        self.assertContains(response, 'id="phase4VampireShopGroup"')
        self.assertContains(response, 'name="adv_adv_vampire"')

    def test_blood_sacrament_is_explicit_temporary_workflow(self):
        CharacterVampireTrait.objects.create(character=self.character, trait=self.blood_sacrament)
        self.character.vampire_intelligent_blood = 5
        self.character.vampire_last_qualifying_kill_day = 0
        self.character.save()
        rules = VampireRules(self.character)
        result = rules.blood_sacrament(2, duration_rounds=3)
        self.assertEqual(result, {"age_bonus": 2, "rounds_remaining": 3})
        self.assertEqual(rules.age_cycle(), 3)
        rules.advance_round()
        rules.advance_round()
        rules.advance_round()
        self.character.refresh_from_db()
        self.assertEqual(self.character.vampire_sacrament_age_bonus, 0)

    def test_strength_extension_preserves_original_premium_threshold(self):
        self.assertEqual(
            calc_attribute_total_cost(19, 21, premium_threshold=16)
            - calc_attribute_total_cost(18, 21, premium_threshold=16),
            20,
        )
        self.character.vampire_age_cycle = 3
        self.character.save(update_fields=["vampire_age_cycle"])
        self.assertEqual(self.character.get_engine(refresh=True).resolve_attribute_cap_bonus(ATTR_ST), 3)

    def _creature(self, **overrides):
        values = {
            "name": f"Vampir-Testkreatur-{Creature.objects.count()}",
            "slug": f"vampir-testkreatur-{Creature.objects.count()}",
            "quality": Quality.objects.get(code=QUALITY_COMMON),
            "combat_speed": 8,
            "march_speed": 16,
            "sprint_speed": 32,
        }
        values.update(overrides)
        return Creature.objects.create(**values)
