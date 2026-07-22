from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.template.loader import render_to_string
from django.urls import reverse

from charsheet.models import Character, Race
from charsheet.sheet_context import _build_damage_gauge_data


class CharacterDamageRulesTests(TestCase):
    def make_character(self, *, stun=0, lethal=0):
        return Character(current_stun_damage=stun, current_lethal_damage=lethal)

    def test_current_damage_is_higher_parallel_track(self):
        character = self.make_character(stun=4, lethal=7)
        self.assertEqual(character.current_damage, 7)

    def test_lethal_does_not_add_to_full_stun_until_it_exceeds_it(self):
        for lethal, expected in ((0, 10), (5, 10), (10, 10), (11, 11)):
            with self.subTest(lethal=lethal):
                self.assertEqual(self.make_character(stun=10, lethal=lethal).current_damage, expected)

    def test_stun_fills_to_maximum(self):
        character = self.make_character(stun=9, lethal=2)
        character.adjust_damage(damage_type="B", action="damage", amount=1, stun_max=10)
        self.assertEqual((character.current_stun_damage, character.current_lethal_damage), (10, 2))

    def test_stun_overflow_advances_lethal_parallel_track(self):
        character = self.make_character(stun=10, lethal=2)
        character.adjust_damage(damage_type="B", action="damage", amount=1, stun_max=10)
        self.assertEqual((character.current_stun_damage, character.current_lethal_damage), (10, 3))
        self.assertEqual(character.current_damage, 10)

    def test_bulk_damage_matches_repeated_single_steps(self):
        for stun in range(0, 11):
            for lethal in (0, 3, 17):
                for amount in range(0, 25):
                    bulk = self.make_character(stun=stun, lethal=lethal)
                    repeated = self.make_character(stun=stun, lethal=lethal)
                    bulk.adjust_damage(damage_type="B", action="damage", amount=amount, stun_max=10)
                    for _index in range(amount):
                        repeated.adjust_damage(damage_type="B", action="damage", amount=1, stun_max=10)
                    self.assertEqual(
                        (bulk.current_stun_damage, bulk.current_lethal_damage),
                        (repeated.current_stun_damage, repeated.current_lethal_damage),
                    )

    def test_healing_only_changes_selected_type(self):
        character = self.make_character(stun=4, lethal=7)
        character.adjust_damage(damage_type="B", action="heal", amount=9, stun_max=10)
        self.assertEqual((character.current_stun_damage, character.current_lethal_damage), (0, 7))
        character.adjust_damage(damage_type="T", action="heal", amount=2, stun_max=10)
        self.assertEqual((character.current_stun_damage, character.current_lethal_damage), (0, 5))

    def test_total_selection_changes_both_tracks(self):
        character = self.make_character(stun=4, lethal=2)
        character.adjust_damage(damage_type="G", action="damage", amount=2, stun_max=10)
        self.assertEqual((character.current_stun_damage, character.current_lethal_damage), (6, 4))
        character.adjust_damage(damage_type="G", action="heal", amount=1, stun_max=10)
        self.assertEqual((character.current_stun_damage, character.current_lethal_damage), (5, 3))

    def test_total_selection_applies_stun_overflow_and_direct_lethal_damage(self):
        character = self.make_character(stun=10, lethal=9)
        character.adjust_damage(damage_type="G", action="damage", amount=1, stun_max=10)
        self.assertEqual((character.current_stun_damage, character.current_lethal_damage), (10, 11))
        self.assertEqual(character.current_damage, 11)


class DamageGaugeDataTests(TestCase):
    def test_equal_values_have_exactly_equal_angles(self):
        gauge = _build_damage_gauge_data(
            current_damage=4,
            threshold_rows=[],
            damage_max=10,
            stun_damage=4,
            lethal_damage=4,
        )
        self.assertEqual(gauge["stun_needle_angle"], gauge["lethal_needle_angle"])

    def test_three_needles_are_calculated_and_clamped_independently(self):
        gauge = _build_damage_gauge_data(
            current_damage=14,
            threshold_rows=[],
            damage_max=10,
            stun_damage=3,
            lethal_damage=14,
        )
        self.assertNotEqual(gauge["stun_needle_angle"], gauge["lethal_needle_angle"])
        self.assertEqual(gauge["lethal_needle_angle"], gauge["total_needle_angle"])

    def test_ignored_penalty_does_not_disable_terminal_stage(self):
        character = type(
            "RenderedCharacter",
            (),
            {"id": 1, "current_stun_damage": 4, "current_lethal_damage": 8, "current_damage": 12},
        )()
        html = render_to_string(
            "charsheet/partials/_damage_panel.html",
            {
                "character": character,
                "current_wound_stage": "Tod",
                "current_wound_penalty": "-6",
                "is_wound_penalty_ignored": True,
                "current_damage_max": 10,
                "damage_gauge_stun_needle_angle": "73",
                "damage_gauge_lethal_needle_angle": "140",
                "damage_gauge_total_needle_angle": "174",
                "damage_gauge_segments": [],
            },
        )
        self.assertIn('class="damage_state_value damage_stage_value" data-stage="Tod"', html)
        self.assertIn("damage_gauge_marker--stun", html)
        self.assertIn("damage_gauge_marker--lethal", html)
        self.assertEqual(html.count("damage_gauge_needle_arm--total"), 1)
        self.assertIn("damage_type_switch_label--total", html)
        self.assertIn('window.localStorage.getItem("charsheet.damageType.1")', html)


class AdjustCurrentDamageViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="damage-user", password="pw")
        self.character = Character.objects.create(
            owner=self.user,
            race=Race.objects.create(name="Damage Race"),
            name="Damage Hero",
            current_stun_damage=10,
            current_lethal_damage=2,
        )
        self.client.force_login(self.user)
        self.url = reverse("adjust_current_damage", args=[self.character.pk])

    @patch("charsheet.engine.character_engine.CharacterEngine.current_wound_penalty", return_value=-1)
    @patch("charsheet.engine.character_engine.CharacterEngine.is_wound_penalty_ignored", return_value=False)
    @patch("charsheet.engine.character_engine.CharacterEngine.current_wound_stage", return_value=("Verletzt", -1))
    @patch("charsheet.engine.character_engine.CharacterEngine.wound_thresholds", return_value={10: ("Verletzt", -1)})
    def test_endpoint_applies_stun_overflow_and_returns_all_values(self, *_mocks):
        response = self.client.post(
            self.url,
            {"damage_type": "B", "action": "damage", "amount": "1", "ajax": "1", "partials": "0"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {key: response.json()[key] for key in ("current_stun_damage", "current_lethal_damage", "current_damage")},
            {"current_stun_damage": 10, "current_lethal_damage": 3, "current_damage": 10},
        )

    @patch("charsheet.engine.character_engine.CharacterEngine.current_wound_penalty", return_value=-1)
    @patch("charsheet.engine.character_engine.CharacterEngine.is_wound_penalty_ignored", return_value=False)
    @patch("charsheet.engine.character_engine.CharacterEngine.current_wound_stage", return_value=("Verletzt", -1))
    @patch("charsheet.engine.character_engine.CharacterEngine.wound_thresholds", return_value={10: ("Verletzt", -1)})
    def test_invalid_type_does_not_change_damage(self, *_mocks):
        response = self.client.post(
            self.url,
            {"damage_type": "X", "action": "damage", "amount": "5", "ajax": "1", "partials": "0"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.character.refresh_from_db()
        self.assertEqual((self.character.current_stun_damage, self.character.current_lethal_damage), (10, 2))
