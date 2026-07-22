from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from charsheet.constants import QUALITY_COMMON, SCHOOL_COMBAT
from charsheet.engine.creature_engine import sync_character_creatures
from charsheet.models import (
    Character,
    CharacterCreature,
    CharacterSchool,
    Creature,
    CreatureSourceBinding,
    Quality,
    Race,
    School,
    SchoolType,
    Technique,
)


class SelectableCreatureBindingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="shape-user", password="pw")
        self.character = Character.objects.create(
            owner=self.user,
            race=Race.objects.create(name="Mensch"),
            name="Alra",
        )
        quality = Quality.objects.get(code=QUALITY_COMMON)
        self.base_creature = Creature.objects.create(
            name="Leere Tierform",
            slug="leere-tierform",
            quality=quality,
            combat_speed=0,
            march_speed=0,
            sprint_speed=0,
        )
        school_type, _ = SchoolType.objects.get_or_create(
            slug=SCHOOL_COMBAT,
            defaults={"name": "Kampfschule"},
        )
        school = School.objects.create(name="Wandler", type=school_type)
        technique = Technique.objects.create(
            name="Tiergestalt",
            school=school,
            level=1,
            acquisition_type=Technique.AcquisitionType.AUTOMATIC,
        )
        CharacterSchool.objects.create(character=self.character, school=school, level=1)
        self.binding = CreatureSourceBinding.objects.create(
            creature=None,
            trigger_type=CreatureSourceBinding.TriggerType.TECHNIQUE,
            technique_trigger=technique,
            selection_mode=CreatureSourceBinding.SelectionMode.CHARACTER_CHOICE,
            quality=quality,
        )

    def test_special_binding_waits_for_character_choice(self):
        creatures = sync_character_creatures(self.character)
        self.assertEqual(len(creatures), 1)
        self.assertEqual(creatures[0].creature.slug, "system-leere-tierform")
        self.assertFalse(creatures[0].source_selection_completed)
        self.client.force_login(self.user)
        response = self.client.get(reverse("character_sheet", args=[self.character.pk]))
        self.assertContains(response, "Tiergestalt auswählen oder erstellen")
        self.assertContains(response, "Leere Karte erstellen")
        self.assertContains(response, 'data-card-holo-kind="creature-shapeshift"')

    def test_free_choice_creates_one_character_card_without_changing_normal_sync(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("choose_technique_creature", args=[self.character.pk, self.binding.pk]),
            {"mode": "free", "custom_name": "Silberfuchs"},
        )

        self.assertRedirects(response, reverse("character_sheet", args=[self.character.pk]))
        card = CharacterCreature.objects.get(owner=self.character, source_binding=self.binding)
        self.assertTrue(card.source_selection_completed)
        self.assertEqual(card.creature.slug, "system-leere-tierform")
        self.assertEqual(card.display_name, "Silberfuchs")
        self.assertEqual(sync_character_creatures(self.character)[0].pk, card.pk)
        response = self.client.get(reverse("character_sheet", args=[self.character.pk]))
        self.assertContains(response, 'data-card-holo-kind="creature-shapeshift"')
        self.assertContains(response, "Silberfuchs Tiergestalt")

    def test_legacy_unfinished_card_does_not_suppress_creation_popover(self):
        CharacterCreature.objects.create(
            owner=self.character,
            creature=self.base_creature,
            source_binding=self.binding,
            source_selection_completed=False,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("character_sheet", args=[self.character.pk]))

        self.assertContains(response, "Tiergestalt auswählen oder erstellen")

    def test_binding_choice_label_controls_creation_card_wording(self):
        self.binding.choice_label = "Tiergefährte"
        self.binding.save(update_fields=["choice_label"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("character_sheet", args=[self.character.pk]))

        self.assertContains(response, "Tiergefährte auswählen oder erstellen")
        self.assertContains(response, "Eigener Name für Tiergefährte")

        self.client.post(
            reverse("choose_technique_creature", args=[self.character.pk, self.binding.pk]),
            {"mode": "template", "creature_id": self.base_creature.pk},
        )
        response = self.client.get(reverse("character_sheet", args=[self.character.pk]))
        self.assertContains(response, "Tiergefährte - Leere Tierform")
        self.assertNotContains(response, 'data-card-holo-kind="creature-shapeshift"')
        self.assertNotContains(response, "Leere Tierform Tiergestalt")

    def test_unlearning_source_school_removes_choice_and_relearning_starts_blank(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse("choose_technique_creature", args=[self.character.pk, self.binding.pk]),
            {"mode": "free", "custom_name": "Silberfuchs"},
        )
        selected_card = CharacterCreature.objects.get(owner=self.character, source_binding=self.binding)
        self.assertTrue(selected_card.source_selection_completed)

        school_entry = CharacterSchool.objects.get(character=self.character, school=self.binding.technique_trigger.school)
        school_entry.delete()
        self.assertEqual(sync_character_creatures(self.character), [])
        self.assertFalse(CharacterCreature.objects.filter(pk=selected_card.pk).exists())

        CharacterSchool.objects.create(
            character=self.character,
            school=self.binding.technique_trigger.school,
            level=1,
        )
        recreated_card = sync_character_creatures(self.character)[0]
        self.assertEqual(recreated_card.creature.slug, "system-leere-tierform")
        self.assertFalse(recreated_card.source_selection_completed)
        self.assertEqual(recreated_card.name_override, "")
