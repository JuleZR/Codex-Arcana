from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from charsheet.constants import QUALITY_COMMON
from charsheet.engine.creature_engine import CreatureEngine
from charsheet.models import Creature, CreatureType, Quality


class CreatureTypeCardTests(TestCase):
    def setUp(self):
        self.quality = Quality.objects.get(code=QUALITY_COMMON)
        self.creature_type = CreatureType.objects.create(name="Baumwesen", slug="baumwesen")

    def create_creature(self, *, name, creature_type=None):
        return Creature.objects.create(
            name=name,
            slug=name.lower().replace(" ", "-"),
            creature_type=creature_type,
            quality=self.quality,
            combat_speed=8,
            march_speed=16,
            sprint_speed=32,
        )

    def test_card_typebar_uses_creature_type_instead_of_creature_name(self):
        creature = self.create_creature(
            name="Baumriese",
            creature_type=self.creature_type,
        )

        context = CreatureEngine(creature).card_context()
        html = render_to_string(
            "charsheet/partials/_creature_card.html",
            {"creature_card": context},
        )

        self.assertEqual(context["creature_type"], "Baumwesen")
        self.assertIn(
            '<span class="card-display-field">Kreatur - Baumwesen</span>',
            html,
        )
        self.assertNotIn("Kreatur - Baumriese", html)

    def test_card_typebar_has_no_empty_separator_without_creature_type(self):
        creature = self.create_creature(name="Formloser Schrecken")

        html = render_to_string(
            "charsheet/partials/_creature_card.html",
            {"creature_card": CreatureEngine(creature).card_context()},
        )

        self.assertIn('<span class="card-display-field">Kreatur</span>', html)
        self.assertNotIn("Kreatur - </span>", html)


class CreatureTypeAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.quality = Quality.objects.get(code=QUALITY_COMMON)
        cls.user = get_user_model().objects.create_superuser(
            username="creature-admin",
            email="creature-admin@example.com",
            password="secret",
        )
        demon = CreatureType.objects.create(name="Dämon", slug="daemon", sort_order=20)
        animal = CreatureType.objects.create(name="Tier", slug="tier", sort_order=10)
        for name, creature_type in (
            ("Zornbrut", demon),
            ("Aschenwicht", demon),
            ("Zottelbär", animal),
            ("Ameisenlöwe", animal),
            ("Namenlos", None),
        ):
            Creature.objects.create(
                name=name,
                slug=name.lower().replace("ä", "ae").replace("ö", "oe"),
                creature_type=creature_type,
                quality=cls.quality,
                combat_speed=8,
                march_speed=16,
                sprint_speed=32,
            )

    def setUp(self):
        self.client.force_login(self.user)

    def test_changelist_has_type_headings_including_empty_type(self):
        response = self.client.get(reverse("admin:charsheet_creature_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="creature-type-group"', count=3)
        self.assertContains(response, "Dämon")
        self.assertContains(response, "Tier")
        self.assertContains(response, "Ohne Kreaturentyp")

    def test_selected_column_sorting_is_applied_inside_each_type_group(self):
        response = self.client.get(
            reverse("admin:charsheet_creature_changelist"),
            {"o": "-1"},
        )

        ordered_rows = [
            (
                creature.creature_type.name if creature.creature_type_id else None,
                creature.name,
            )
            for creature in response.context["cl"].result_list
        ]

        self.assertEqual(
            ordered_rows,
            [
                ("Tier", "Zottelbär"),
                ("Tier", "Ameisenlöwe"),
                ("Dämon", "Zornbrut"),
                ("Dämon", "Aschenwicht"),
                (None, "Namenlos"),
            ],
        )
