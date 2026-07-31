from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from charsheet.engine.character_engine import CharacterEngine
from charsheet.engine.creature_engine import CreatureEngine
from charsheet.learning import _reset_invalid_school_progression, process_learning_submission
from charsheet.learning_progression import build_learning_progression_context
from charsheet.models import (
    Attribute,
    Character,
    CharacterAttribute,
    CharacterCreature,
    CharacterCreatureDaemonicPower,
    CharacterDaemonicPower,
    CharacterSchool,
    CharacterTechnique,
    Creature,
    DaemonicPower,
    DaemonicPowerSemanticEffect,
    DaemonicPowerTier,
    Race,
    School,
    SchoolType,
    Technique,
    TechniqueRequirement,
)
from charsheet.sheet_context import (
    _build_daemonic_power_panel,
    build_creature_card_training_context,
)


class DaemonicPowerTests(TestCase):
    """Regression coverage for character and creature daemonic powers."""

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="daemonic-power-user",
            password="test12345",
        )
        self.race = Race.objects.create(name="Daemonic Test Race")
        self.character = Character.objects.create(
            owner=self.user,
            name="Nyx",
            race=self.race,
        )
        self.perception = Attribute.objects.create(
            name="Daemonic Test Wahrnehmung",
            short_name="WA",
        )
        CharacterAttribute.objects.create(
            character=self.character,
            attribute=self.perception,
            base_value=5,
        )
        self.school_type = SchoolType.objects.create(
            name="Daemonic Test School Type",
            slug="daemonic-test-school-type",
        )
        self.school = School.objects.create(
            name="Geschenke der Finsternis",
            type=self.school_type,
        )
        self.school_entry = CharacterSchool.objects.create(
            character=self.character,
            school=self.school,
            level=3,
        )
        self.tier_one = DaemonicPowerTier.objects.create(
            name="Nieder",
            slug="nieder",
            sort_number=10,
        )
        self.tier_two = DaemonicPowerTier.objects.create(
            name="Hoch",
            slug="hoch",
            sort_number=20,
        )
        self.shadow = DaemonicPower.objects.create(
            name="Schattenhaut",
            slug="schattenhaut",
            tier=self.tier_one,
            description="Die Haut verschmilzt mit tiefen Schatten.",
            weakness_description="Geweihtes Licht verursacht Schmerzen.",
        )
        self.claws = DaemonicPower.objects.create(
            name="Dämonenklauen",
            slug="daemonenklauen",
            tier=self.tier_one,
            description="Lange Klauen wachsen aus den Händen.",
            weakness_description="Die Hände können nichts Zartes berühren.",
        )
        self.wings = DaemonicPower.objects.create(
            name="Schwingen der Tiefe",
            slug="schwingen-der-tiefe",
            tier=self.tier_two,
            description="Dunkle Schwingen tragen den Körper.",
            weakness_description="Kann geweihte Schwellen nicht überfliegen.",
        )
        self.camouflage = DaemonicPower.objects.create(
            name="Tarnung",
            slug="tarnung",
            tier=self.tier_one,
            description="Die Gestalt passt sich ihrer Umgebung an.",
            weakness_description="Helles Licht bricht die Tarnung.",
        )

    def _granting_technique(self, name, tier, *, acquisition_type=Technique.AcquisitionType.AUTOMATIC):
        return Technique.objects.create(
            name=name,
            school=self.school,
            level=1,
            acquisition_type=acquisition_type,
            granted_daemonic_power_tier=tier,
        )

    def test_effect_scope_rejects_creature_target_for_character_or_both(self):
        field_names = [
            field.name
            for field in DaemonicPower._meta.fields
        ]
        self.assertLess(
            field_names.index("description"),
            field_names.index("weakness_description"),
        )
        effect = DaemonicPowerSemanticEffect(
            power=self.shadow,
            application_scope=DaemonicPowerSemanticEffect.ApplicationScope.BOTH,
            target_domain="creature_attack_damage",
            target_key="bite",
            value="2",
        )

        with self.assertRaises(ValidationError):
            effect.full_clean()

    def test_multiple_grants_create_independent_choices_and_ownerships(self):
        first = self._granting_technique("Erstes Geschenk", self.tier_one)
        second = self._granting_technique("Zweites Geschenk", self.tier_two)
        third = self._granting_technique("Drittes Geschenk", self.tier_one)
        context = build_learning_progression_context(
            self.character,
            engine=self.character.get_engine(refresh=True),
        )
        decisions = [
            decision
            for decision in context["learn_pending_decisions"]
            if decision["kind"] == "daemonic_power"
        ]

        self.assertEqual(
            {decision["decision_id"] for decision in decisions},
            {
                f"daemonic-power-{first.id}",
                f"daemonic-power-{second.id}",
                f"daemonic-power-{third.id}",
            },
        )
        first_decision = next(
            decision
            for decision in decisions
            if decision["decision_id"] == f"daemonic-power-{first.id}"
        )
        shadow_option = next(
            option
            for option in first_decision["options"]
            if option["submit_value"] == str(self.shadow.id)
        )
        self.assertEqual(shadow_option["description"], self.shadow.description)
        self.assertEqual(
            shadow_option["facts"],
            [
                {
                    "label": "Schwäche",
                    "value": self.shadow.weakness_description,
                }
            ],
        )
        result, _message = process_learning_submission(
            self.character,
            {
                f"learn_choice_daemonic_power_{first.id}": str(self.shadow.id),
                f"learn_choice_daemonic_power_{second.id}": str(self.wings.id),
                f"learn_choice_daemonic_power_{third.id}": str(self.claws.id),
            },
        )

        self.assertEqual(result, "success")
        self.assertEqual(
            set(
                CharacterDaemonicPower.objects.filter(character=self.character)
                .values_list("granting_technique_id", "power_id")
            ),
            {
                (first.id, self.shadow.id),
                (second.id, self.wings.id),
                (third.id, self.claws.id),
            },
        )

    def test_learning_rejects_wrong_tier_and_duplicate_power(self):
        first = self._granting_technique("Doppeltes Geschenk I", self.tier_one)
        second = self._granting_technique("Doppeltes Geschenk II", self.tier_one)

        wrong_result, _message = process_learning_submission(
            self.character,
            {f"learn_choice_daemonic_power_{first.id}": str(self.wings.id)},
        )
        self.assertEqual(wrong_result, "error")
        self.assertFalse(CharacterDaemonicPower.objects.exists())

        duplicate_result, _message = process_learning_submission(
            self.character,
            {
                f"learn_choice_daemonic_power_{first.id}": str(self.shadow.id),
                f"learn_choice_daemonic_power_{second.id}": str(self.shadow.id),
            },
        )
        self.assertEqual(duplicate_result, "error")
        self.assertFalse(CharacterDaemonicPower.objects.exists())

    def test_learning_rejects_granting_technique_not_owned_by_character(self):
        foreign_school = School.objects.create(
            name="Fremde Dämonenschule",
            type=self.school_type,
        )
        foreign_technique = Technique.objects.create(
            name="Fremdes Geschenk",
            school=foreign_school,
            level=1,
            granted_daemonic_power_tier=self.tier_one,
        )

        result, _message = process_learning_submission(
            self.character,
            {
                f"learn_choice_daemonic_power_{foreign_technique.id}": str(
                    self.shadow.id
                )
            },
        )

        self.assertEqual(result, "error")
        self.assertFalse(CharacterDaemonicPower.objects.exists())

    def test_grant_tier_change_disables_old_choice_and_replaces_it(self):
        technique = self._granting_technique("Wandelbares Geschenk", self.tier_one)
        CharacterDaemonicPower.objects.create(
            character=self.character,
            power=self.shadow,
            granting_technique=technique,
        )
        technique.granted_daemonic_power_tier = self.tier_two
        technique.save(update_fields=["granted_daemonic_power_tier"])

        context = build_learning_progression_context(
            self.character,
            engine=self.character.get_engine(refresh=True),
        )
        decision = next(
            decision
            for decision in context["learn_pending_decisions"]
            if decision["decision_id"] == f"daemonic-power-{technique.id}"
        )
        self.assertEqual(
            {option["submit_value"] for option in decision["options"]},
            {str(self.wings.id)},
        )
        self.assertEqual(
            _build_daemonic_power_panel(
                self.character,
                self.character.get_engine(refresh=True),
            ),
            [],
        )

        result, _message = process_learning_submission(
            self.character,
            {
                f"learn_choice_daemonic_power_{technique.id}": str(
                    self.wings.id
                )
            },
        )

        self.assertEqual(result, "success")
        ownership = CharacterDaemonicPower.objects.get(
            character=self.character,
            granting_technique=technique,
        )
        self.assertEqual(ownership.power, self.wings)

    def test_permanent_loss_deletes_choice_but_temporary_requirement_loss_keeps_it(self):
        technique = self._granting_technique(
            "Wankendes Geschenk",
            self.tier_one,
            acquisition_type=Technique.AcquisitionType.CHOICE,
        )
        learned = CharacterTechnique.objects.create(
            character=self.character,
            technique=technique,
        )
        CharacterDaemonicPower.objects.create(
            character=self.character,
            power=self.shadow,
            granting_technique=technique,
        )
        TechniqueRequirement.objects.create(
            technique=technique,
            minimum_school_level=4,
        )

        _reset_invalid_school_progression(self.character)

        self.assertTrue(CharacterTechnique.objects.filter(pk=learned.pk).exists())
        self.assertTrue(
            CharacterDaemonicPower.objects.filter(
                character=self.character,
                granting_technique=technique,
            ).exists()
        )
        self.assertEqual(
            _build_daemonic_power_panel(
                self.character,
                self.character.get_engine(refresh=True),
            ),
            [],
        )

        learned.delete()

        self.assertFalse(
            CharacterDaemonicPower.objects.filter(
                character=self.character,
                granting_technique=technique,
            ).exists()
        )

    def test_character_and_creature_effect_scopes_are_isolated(self):
        technique = self._granting_technique("Semantisches Geschenk", self.tier_one)
        CharacterDaemonicPower.objects.create(
            character=self.character,
            power=self.shadow,
            granting_technique=technique,
        )
        creature = Creature.objects.create(
            name="Dämonischer Testwolf",
            slug="daemonischer-testwolf",
            initiative_override=5,
        )
        creature.daemonic_powers.add(self.shadow)
        DaemonicPowerSemanticEffect.objects.create(
            power=self.shadow,
            application_scope=DaemonicPowerSemanticEffect.ApplicationScope.BOTH,
            target_domain="derived_stat",
            target_key="initiative",
            value="2",
            sort_order=1,
        )
        DaemonicPowerSemanticEffect.objects.create(
            power=self.shadow,
            application_scope=DaemonicPowerSemanticEffect.ApplicationScope.CHARACTER,
            target_domain="derived_stat",
            target_key="initiative",
            value="3",
            sort_order=2,
        )
        DaemonicPowerSemanticEffect.objects.create(
            power=self.shadow,
            application_scope=DaemonicPowerSemanticEffect.ApplicationScope.CREATURE,
            target_domain="derived_stat",
            target_key="initiative",
            value="4",
            sort_order=3,
        )

        character_engine = CharacterEngine(self.character)
        self.assertEqual(
            character_engine.modifier_engine.resolve_numeric_total(
                "derived_stat",
                "initiative",
            ),
            5,
        )
        self.assertEqual(CreatureEngine(creature).initiative(), 11)

    def test_power_effects_use_existing_stack_resolution(self):
        technique = self._granting_technique("Gestapeltes Geschenk", self.tier_one)
        CharacterDaemonicPower.objects.create(
            character=self.character,
            power=self.shadow,
            granting_technique=technique,
        )
        for sort_order, value in ((2, "5"), (1, "2")):
            DaemonicPowerSemanticEffect.objects.create(
                power=self.shadow,
                application_scope=DaemonicPowerSemanticEffect.ApplicationScope.CHARACTER,
                target_domain="derived_stat",
                target_key="initiative",
                value=value,
                stack_behavior="unique_by_source",
                sort_order=sort_order,
            )

        engine = CharacterEngine(self.character)

        self.assertEqual(
            engine.modifier_engine.resolve_numeric_total(
                "derived_stat",
                "initiative",
            ),
            2,
        )
        self.assertEqual(
            [
                modifier.value
                for modifier in engine.modifier_engine._active_daemonic_power_modifiers
            ],
            [2, 5],
        )

    def test_power_effect_can_apply_minus_two_to_another_daemonic_power(self):
        source_technique = self._granting_technique(
            "Quelle der Tarnschwäche",
            self.tier_one,
        )
        target_technique = self._granting_technique(
            "Tarnendes Geschenk",
            self.tier_one,
        )
        CharacterDaemonicPower.objects.create(
            character=self.character,
            power=self.claws,
            granting_technique=source_technique,
        )
        CharacterDaemonicPower.objects.create(
            character=self.character,
            power=self.camouflage,
            granting_technique=target_technique,
        )
        effect = DaemonicPowerSemanticEffect.objects.create(
            power=self.claws,
            application_scope=DaemonicPowerSemanticEffect.ApplicationScope.BOTH,
            target_domain="daemonic_power",
            target_key=self.camouflage.slug,
            value="-2",
        )
        creature = Creature.objects.create(
            name="Getarnter Testdämon",
            slug="getarnter-testdaemon",
        )
        creature.daemonic_powers.add(self.claws, self.camouflage)

        character_panel = _build_daemonic_power_panel(
            self.character,
            self.character.get_engine(refresh=True),
        )
        character_camouflage = next(
            power
            for group in character_panel
            for power in group["powers"]
            if power["id"] == self.camouflage.id
        )
        creature_camouflage = next(
            power
            for power in CreatureEngine(creature).daemonic_powers()
            if power["id"] == self.camouflage.id
        )

        self.assertEqual(character_camouflage["modifier"], -2)
        self.assertEqual(character_camouflage["modifier_display"], "-2")
        self.assertEqual(creature_camouflage["modifier"], -2)
        self.assertEqual(creature_camouflage["modifier_display"], "-2")

        from charsheet.admin import DaemonicPowerSemanticEffectAdminForm

        form = DaemonicPowerSemanticEffectAdminForm(instance=effect)
        target_values = {
            value
            for value, _label in form.fields["simple_target"].choices
        }
        self.assertIn(f"daemonic_power:{self.camouflage.slug}", target_values)
        self.assertEqual(form.initial["effect_area"], "daemonic_power")
        self.assertEqual(
            form.initial["simple_target"],
            f"daemonic_power:{self.camouflage.slug}",
        )

    def test_power_effect_rejects_unknown_daemonic_power_target(self):
        effect = DaemonicPowerSemanticEffect(
            power=self.claws,
            application_scope=DaemonicPowerSemanticEffect.ApplicationScope.BOTH,
            target_domain="daemonic_power",
            target_key="does-not-exist",
            value="-2",
        )

        with self.assertRaises(ValidationError):
            effect.full_clean()

    def test_creature_training_uses_union_and_protects_base_power(self):
        creature = Creature.objects.create(
            name="Ausbildungsdämon",
            slug="ausbildungsdaemon",
        )
        creature.daemonic_powers.add(self.shadow)
        card = CharacterCreature.objects.create(
            owner=self.character,
            creature=creature,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("update_character_creature_training", kwargs={"pk": card.pk}),
            {
                "daemonic_powers_present": "1",
                "daemonic_powers": [str(self.shadow.id), str(self.wings.id)],
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(card.daemonic_power_additions.values_list("power_id", flat=True)),
            {self.wings.id},
        )
        self.assertEqual(
            [row["id"] for row in CreatureEngine(card).daemonic_powers()],
            [self.shadow.id, self.wings.id],
        )

        response = self.client.post(
            reverse("update_character_creature_training", kwargs={"pk": card.pk}),
            {"daemonic_powers_present": "1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CharacterCreatureDaemonicPower.objects.filter(creature=card).exists())
        self.assertEqual(
            [row["id"] for row in CreatureEngine(card).daemonic_powers()],
            [self.shadow.id],
        )
        context = build_creature_card_training_context(card)
        base_row = next(
            row
            for group in context["daemonic_power_groups"]
            for row in group["powers"]
            if row["id"] == self.shadow.id
        )
        self.assertTrue(base_row["selected"])
        self.assertTrue(base_row["is_base"])

    def test_creature_training_rejects_foreign_character_card(self):
        other_user = get_user_model().objects.create_user(
            username="other-daemonic-user",
            password="test12345",
        )
        other_character = Character.objects.create(
            owner=other_user,
            name="Fremde Nyx",
            race=self.race,
        )
        creature = Creature.objects.create(
            name="Fremder Ausbildungsdämon",
            slug="fremder-ausbildungsdaemon",
        )
        foreign_card = CharacterCreature.objects.create(
            owner=other_character,
            creature=creature,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "update_character_creature_training",
                kwargs={"pk": foreign_card.pk},
            ),
            {
                "daemonic_powers_present": "1",
                "daemonic_powers": [str(self.shadow.id)],
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            CharacterCreatureDaemonicPower.objects.filter(
                creature=foreign_card,
            ).exists()
        )

    def test_character_panel_sorts_tiers_then_power_names(self):
        technique_b = self._granting_technique("Sortiergeschenk B", self.tier_one)
        technique_a = self._granting_technique("Sortiergeschenk A", self.tier_one)
        technique_high = self._granting_technique("Sortiergeschenk Hoch", self.tier_two)
        CharacterDaemonicPower.objects.create(
            character=self.character,
            power=self.shadow,
            granting_technique=technique_b,
        )
        CharacterDaemonicPower.objects.create(
            character=self.character,
            power=self.claws,
            granting_technique=technique_a,
        )
        CharacterDaemonicPower.objects.create(
            character=self.character,
            power=self.wings,
            granting_technique=technique_high,
        )

        panel = _build_daemonic_power_panel(
            self.character,
            self.character.get_engine(refresh=True),
        )

        self.assertEqual([group["name"] for group in panel], ["Nieder", "Hoch"])
        self.assertEqual(
            [power["name"] for power in panel[0]["powers"]],
            ["Dämonenklauen", "Schattenhaut"],
        )

    def test_character_sheet_and_creature_card_render_power_sections(self):
        technique = self._granting_technique("Sichtbares Geschenk", self.tier_one)
        CharacterDaemonicPower.objects.create(
            character=self.character,
            power=self.shadow,
            granting_technique=technique,
        )
        creature = Creature.objects.create(
            name="Sichtbarer Dämon",
            slug="sichtbarer-daemon",
        )
        creature.daemonic_powers.add(self.claws)
        card = CharacterCreature.objects.create(
            owner=self.character,
            creature=creature,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "character_sheet",
                kwargs={"character_id": self.character.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-tab-target="lowerPanelDaemonicPowers"')
        self.assertContains(response, self.shadow.name)
        self.assertContains(response, self.shadow.description)
        self.assertContains(response, self.shadow.weakness_description)

        read_only_card_html = render_to_string(
            "charsheet/partials/_creature_card.html",
            {"creature_card": CreatureEngine(card).card_context()},
        )
        self.assertIn("D&auml;monische Kr&auml;fte", read_only_card_html)
        self.assertIn(self.claws.name, read_only_card_html)
        self.assertIn(self.claws.description, read_only_card_html)
        self.assertIn(self.claws.weakness_description, read_only_card_html)
