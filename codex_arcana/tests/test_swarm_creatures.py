from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from charsheet.constants import QUALITY_COMMON
from charsheet.engine.creature_engine import CreatureEngine
from charsheet.models import (
    Character,
    CharacterCreature,
    Creature,
    CreatureAttack,
    CreatureSwarmAttackOverride,
    CreatureSwarmCountEffect,
    CreatureSwarmProfile,
    Quality,
    Race,
)


class SwarmCreatureTests(TestCase):
    def setUp(self):
        self.quality, _created = Quality.objects.get_or_create(
            code=QUALITY_COMMON,
            defaults={"name": "Gewoehnlich", "is_default": True},
        )

    def creature(self, name, size_class="M"):
        return Creature.objects.create(
            name=name,
            slug=name.lower().replace(" ", "-"),
            quality=self.quality,
            size_class=size_class,
            is_swarm_creature=True,
            initiative_override=3,
            vw_override=12,
            sr_override=10,
            gw_override=8,
            combat_speed=1,
            march_speed=2,
            sprint_speed=3,
        )

    def test_flesh_eating_flies_resolve_both_size_classes_and_grw_divisor(self):
        flies = self.creature("Fleischfressende Fliegen")
        bite = CreatureAttack.objects.create(
            creature=flies,
            name="Biss",
            attack_value=2,
            damage_dice_amount=1,
            damage_dice_faces=10,
        )
        profile = CreatureSwarmProfile.objects.create(
            creature=flies,
            individual_size_class="S",
            swarm_size_class="M",
        )
        CreatureSwarmAttackOverride.objects.create(
            profile=profile,
            base_attack=bite,
            attack_value_override=10,
        )
        self.assertEqual(CreatureEngine(flies).size_class(), "M")
        self.assertEqual(CreatureEngine(flies).attacks()[0]["attack_value"], 10)
        self.assertEqual(CreatureEngine(flies).normal_weapon_damage_divisor(), 8)
        profile.default_display_mode = CreatureSwarmProfile.DisplayMode.INDIVIDUAL
        profile.save(update_fields=["default_display_mode"])
        self.assertEqual(CreatureEngine(flies).size_class(), "S")
        self.assertEqual(CreatureEngine(flies).attacks()[0]["attack_value"], 10)

    def test_swarm_json_override_help_lists_format_and_supported_keys(self):
        from charsheet.admin import CreatureSwarmProfileAdminForm

        form = CreatureSwarmProfileAdminForm()
        help_text = str(form.fields["swarm_overrides"].help_text)
        self.assertIn("(?)", help_text)
        self.assertIn("initiative_override", help_text)
        self.assertIn("combat_speed", help_text)

    def test_pelzwespe_resolves_wounds_attack_and_count_rules(self):
        wasp = self.creature("Pelzwespe", size_class="K")
        attack = CreatureAttack.objects.create(
            creature=wasp, name="Stachel", attack_value=6,
            damage_dice_amount=1, damage_dice_faces=4,
        )
        profile = CreatureSwarmProfile.objects.create(
            creature=wasp,
            individual_size_class="F",
            swarm_size_class="K",
            individual_life_points=1,
            swarm_wound_thresholds="10,20,30,40,50,60",
            max_swarm_count=35,
        )
        CreatureSwarmAttackOverride.objects.create(
            profile=profile, base_attack=attack,
            name_override="Stachelschwarm", damage_dice_amount_override=2,
        )
        CreatureSwarmCountEffect.objects.create(
            profile=profile, label="Giftstaerke", target_key="poison-strength", interval=2,
        )
        CreatureSwarmCountEffect.objects.create(
            profile=profile, label="Giftschaden", target_key="poison-damage", interval=5,
        )
        user = get_user_model().objects.create_user(username="swarm-owner", password="pw")
        character = Character.objects.create(owner=user, race=Race.objects.create(name="Mensch"), name="Alra")
        card = CharacterCreature.objects.create(
            owner=character, creature=wasp, swarm_mode="individual", current_swarm_count=35,
        )
        individual = CreatureEngine(card)
        self.assertEqual(individual.size_class(), "F")
        self.assertEqual(individual.wound_rows(), [{"label": "LP", "threshold": 1, "penalty": 0}])

        card.swarm_mode = "swarm"
        card.save(update_fields=["swarm_mode"])
        swarm = CreatureEngine(card)
        self.assertEqual(swarm.size_class(), "K")
        self.assertEqual([row["threshold"] for row in swarm.wound_rows()], [10, 20, 30, 40, 50, 60])
        self.assertEqual(swarm.attacks()[0]["name"], "Stachelschwarm")
        self.assertTrue(swarm.attacks()[0]["damage_display"].startswith("2w4"))
        bonuses = {row["target_key"]: row["bonus"] for row in swarm.swarm_count_effects()}
        self.assertEqual(bonuses, {"poison-strength": 17, "poison-damage": 7})
        self.assertEqual(swarm.normal_weapon_damage_divisor(), 4)

        card.size_class_override = "W"
        card.save(update_fields=["size_class_override"])
        self.assertEqual(CreatureEngine(card).size_class(), "W")

    def test_swarm_only_coastal_bee_needs_no_individual_profile(self):
        bee = self.creature("Kuestenbiene")
        CreatureSwarmProfile.objects.create(
            creature=bee,
            individual_mode_available=False,
            swarm_size_class="M",
            min_swarm_count=30,
            max_swarm_count=50,
        )
        context = CreatureEngine(bee).card_context()
        self.assertEqual(context["swarm_mode"], "swarm")
        self.assertFalse(context["swarm_individual_available"])
        self.assertFalse(context["swarm_has_mode_switch"])
        self.assertEqual((context["min_swarm_count"], context["max_swarm_count"]), (30, 50))

    def test_mode_endpoint_updates_same_character_creature(self):
        creature = self.creature("Modusschwarm")
        CreatureSwarmProfile.objects.create(
            creature=creature, individual_size_class="F", swarm_size_class="K",
        )
        user = get_user_model().objects.create_user(username="switch-owner", password="pw")
        character = Character.objects.create(owner=user, race=Race.objects.create(name="Elf"), name="Lira")
        card = CharacterCreature.objects.create(owner=character, creature=creature)
        self.client.force_login(user)
        response = self.client.post(
            reverse("update_character_creature_swarm", kwargs={"pk": card.pk}),
            {"mode": "individual", "current_swarm_count": "12"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        card.refresh_from_db()
        self.assertEqual(card.swarm_mode, "individual")
        self.assertEqual(card.current_swarm_count, 12)
        self.assertEqual(CharacterCreature.objects.filter(pk=card.pk).count(), 1)
        self.assertContains(response, "Einzeltier")

        response = self.client.post(
            reverse("update_character_creature_swarm", kwargs={"pk": card.pk}),
            {"mode": "swarm", "current_swarm_count": ""},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        card.refresh_from_db()
        self.assertIsNone(card.current_swarm_count)
        card_html = response.json()["cardHtml"]
        self.assertEqual(card_html.count('<button class="creature-card__swarm-toggle'), 1)
        self.assertNotIn("data-swarm-count-input", card_html)

    def test_edit_mode_stores_individual_and_swarm_images_separately(self):
        creature = self.creature("Bildschwarm")
        profile = CreatureSwarmProfile.objects.create(
            creature=creature,
            individual_size_class="F",
            swarm_size_class="K",
            image="creatures/swarms/template-swarm.png",
        )
        user = get_user_model().objects.create_user(username="image-owner", password="pw")
        character = Character.objects.create(owner=user, race=Race.objects.create(name="Fee"), name="Mira")
        card = CharacterCreature.objects.create(owner=character, creature=creature, swarm_mode="swarm")
        self.client.force_login(user)
        update_url = reverse("update_character_creature_training", kwargs={"pk": card.pk})

        def save_fake_image(instance, field_name, _cropped_data, _base_name):
            setattr(instance, field_name, f"character_creatures/{field_name}.png")
            return True

        with patch("charsheet.views._save_cropped_card_image", side_effect=save_fake_image):
            response = self.client.post(
                update_url,
                {
                    "custom_creature_image_mode": "swarm",
                    "custom_creature_image_cropped_data": "data:image/png;base64,c3dhcm0=",
                },
            )
        self.assertEqual(response.status_code, 200)
        card.refresh_from_db()
        self.assertTrue(card.swarm_image_override.name.endswith("swarm_image_override.png"))
        self.assertFalse(card.image_override)

        card.swarm_mode = "individual"
        card.save(update_fields=["swarm_mode"])
        with patch("charsheet.views._save_cropped_card_image", side_effect=save_fake_image):
            response = self.client.post(
                update_url,
                {
                    "custom_creature_image_mode": "individual",
                    "custom_creature_image_cropped_data": "data:image/png;base64,aW5kaXZpZHVhbA==",
                },
            )
        self.assertEqual(response.status_code, 200)
        card.refresh_from_db()
        self.assertTrue(card.image_override.name.endswith("image_override.png"))
        self.assertTrue(card.swarm_image_override.name.endswith("swarm_image_override.png"))
        self.assertEqual(CreatureEngine(card).image().name, card.image_override.name)

        card.swarm_mode = "swarm"
        card.swarm_image_override = None
        card.save(update_fields=["swarm_mode", "swarm_image_override"])
        self.assertEqual(CreatureEngine(card).image().name, profile.image.name)
